"""Adapter tests. Fixtures follow the vendors' documented response shapes (not captured live traffic)."""

import json

import httpx
import pytest

from vistrack.config import Market
from vistrack.engines.anthropic_engine import AnthropicEngine
from vistrack.engines.dataforseo_engine import GoogleAiModeEngine, GoogleAioEngine
from vistrack.engines.openai_engine import OpenAIEngine
from vistrack.engines.perplexity_engine import PerplexityEngine

MARKET = Market("Austin", "Texas", "US", "America/Chicago", 30.27, -97.74, "Austin,Texas,United States")


def client_returning(payload, status=200, capture=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if capture is not None:
            capture["request"] = request
        return httpx.Response(status, json=payload)

    return httpx.Client(transport=httpx.MockTransport(handler))


OPENAI_OK = {
    "output": [
        {"type": "web_search_call", "action": {"sources": [{"url": "https://yelp.com/a"}, {"url": "https://b.com/"}]}},
        {
            "type": "message",
            "content": [
                {
                    "type": "output_text",
                    "text": "Try Practice D Dental.",
                    "annotations": [{"type": "url_citation", "url": "https://practice-d.example/", "title": "LBD"}],
                }
            ],
        },
    ],
    "usage": {"input_tokens": 10000, "output_tokens": 500},
}


def test_openai_parse_cost_and_citations():
    r = OpenAIEngine(client=client_returning({})).parse(OPENAI_OK)
    assert r.status == "ok" and "Practice D" in r.answer_text and r.searches == 1
    kinds = {c.url: c.kind for c in r.citations}
    assert kinds["https://practice-d.example/"] == "cited" and kinds["https://yelp.com/a"] == "consulted"
    assert r.cost_usd == pytest.approx(10000 * 0.75e-6 + 500 * 4.5e-6 + 0.01)


def test_openai_request_has_location_search_tool_and_key_header(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    cap = {}
    eng = OpenAIEngine(client=client_returning(OPENAI_OK, capture=cap))
    eng.query("best dentist", MARKET)
    req = cap["request"]
    body = json.loads(req.content)
    tool = body["tools"][0]
    assert tool["type"] == "web_search" and tool["user_location"]["city"] == "Austin"
    assert tool["user_location"]["type"] == "approximate"
    assert "web_search_call.action.sources" in body["include"]
    assert req.headers["authorization"] == "Bearer sk-test-not-real"


def test_http_429_is_retryable_error(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    res = OpenAIEngine(client=client_returning({"error": "slow down"}, status=429)).query("q", MARKET)
    assert res.status == "error" and res.retryable and res.http_status == 429


ANTHROPIC_OK = {
    "content": [
        {"type": "server_tool_use", "name": "web_search"},
        {
            "type": "web_search_tool_result",
            "content": [{"type": "web_search_result", "url": "https://zocdoc.com/x", "title": "Z"}],
        },
        {
            "type": "text",
            "text": "Practice F Dental is an option.",
            "citations": [{"type": "web_search_result_location", "url": "https://practice-f.example/", "title": "B"}],
        },
    ],
    "usage": {"input_tokens": 8000, "output_tokens": 300, "server_tool_use": {"web_search_requests": 2}},
}


def test_anthropic_parse():
    r = AnthropicEngine(client=client_returning({})).parse(ANTHROPIC_OK)
    assert r.status == "ok" and r.searches == 2
    assert {c.url: c.kind for c in r.citations} == {
        "https://practice-f.example/": "cited",
        "https://zocdoc.com/x": "consulted",
    }
    assert r.cost_usd == pytest.approx(8000 * 0.10e-6 + 300 * 0.50e-6 + 0.02)


def test_anthropic_search_error_inside_http_200_is_an_error_not_a_miss():
    payload = {
        "content": [
            {
                "type": "web_search_tool_result",
                "content": {"type": "web_search_tool_result_error", "error_code": "too_many_requests"},
            },
            {"type": "text", "text": "I could not search."},
        ],
        "usage": {},
    }
    r = AnthropicEngine(client=client_returning({})).parse(payload)
    assert r.status == "error" and r.retryable and "too_many_requests" in r.error


def test_anthropic_api_error_object():
    r = AnthropicEngine(client=client_returning({})).parse({"type": "error", "error": {"message": "bad model"}})
    assert r.status == "error" and not r.retryable


PERPLEXITY_OK = {
    "output": [
        {
            "type": "search_results",
            "results": [
                {"id": 1, "url": "https://a.com/", "title": "A"},
                {"id": 2, "url": "https://b.com/", "title": "B"},
            ],
        },
        {"type": "message", "content": [{"type": "output_text", "text": "Practice E Dentistry is popular [2]."}]},
    ],
    "usage": {"input_tokens": 4000, "output_tokens": 200, "tool_calls_details": {"search_web": {"invocation": 1}}},
}


def test_perplexity_only_marked_sources_are_cited():
    r = PerplexityEngine(client=client_returning({})).parse(PERPLEXITY_OK)
    assert {c.url: c.kind for c in r.citations} == {"https://a.com/": "consulted", "https://b.com/": "cited"}
    assert r.searches == 1 and r.cost_usd > 0


DFS_AIO = {
    "status_code": 20000,
    "cost": 0.004,
    "tasks": [
        {
            "status_code": 20000,
            "result": [
                {
                    "items": [
                        {"type": "organic"},
                        {
                            "type": "ai_overview",
                            "markdown": "Practice A Smiles is often listed.",
                            "references": [{"url": "https://practice-a.example/", "title": "AES"}],
                        },
                    ]
                }
            ],
        }
    ],
}


def test_dataforseo_parse_overview_and_cost():
    r = GoogleAioEngine(client=client_returning({})).parse(DFS_AIO)
    assert r.status == "ok" and r.answer_present and r.cost_usd == 0.004
    assert r.citations[0].url == "https://practice-a.example/"


def test_dataforseo_absent_overview_is_ok_but_not_present():
    payload = {
        "status_code": 20000,
        "cost": 0.002,
        "tasks": [{"status_code": 20000, "result": [{"items": [{"type": "organic"}]}]}],
    }
    r = GoogleAiModeEngine(client=client_returning({})).parse(payload)
    assert r.status == "ok" and not r.answer_present and r.answer_text == ""


def test_dataforseo_task_error():
    payload = {"status_code": 20000, "tasks": [{"status_code": 40501, "status_message": "Invalid Field"}]}
    r = GoogleAioEngine(client=client_returning({})).parse(payload)
    assert r.status == "error" and not r.retryable


def test_dataforseo_request_shape(monkeypatch):
    monkeypatch.setenv("DATAFORSEO_LOGIN", "u")
    monkeypatch.setenv("DATAFORSEO_PASSWORD", "p")
    cap = {}
    GoogleAioEngine(client=client_returning(DFS_AIO, capture=cap)).query("best dentist", MARKET)
    body = json.loads(cap["request"].content)[0]
    assert body["load_async_ai_overview"] is True and body["location_name"] == "Austin,Texas,United States"
    assert cap["request"].headers["authorization"].startswith("Basic ")


def test_missing_env_reported_without_values(monkeypatch):
    monkeypatch.delenv("DATAFORSEO_LOGIN", raising=False)
    monkeypatch.setenv("DATAFORSEO_PASSWORD", "p")
    eng = GoogleAioEngine(client=client_returning({}))
    assert eng.missing_env() == ["DATAFORSEO_LOGIN"] and not eng.available()
