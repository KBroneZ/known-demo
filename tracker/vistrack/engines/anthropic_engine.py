"""Anthropic Messages API + web_search_20250305 tool."""

from __future__ import annotations

import os

from ..config import Market
from .base import Citation, Engine, RawResult, dedupe_citations, error_result

URL = "https://api.anthropic.com/v1/messages"
SEARCH_USD = 0.010
RETRYABLE_SEARCH_ERRORS = {"too_many_requests", "unavailable"}


class AnthropicEngine(Engine):
    key = "anthropic"
    label = "Claude (Anthropic API)"
    tool_version = "web_search_20250305"
    env_vars = ("ANTHROPIC_API_KEY",)
    est_cost_upper = 0.033
    default_model = "claude-haiku-5-5"  # model id from research 04; verify before the real run

    def query(self, prompt: str, market: Market) -> RawResult:
        body = {
            "model": self.model,
            "max_tokens": self.params.get("max_tokens", 1500),
            "messages": [{"role": "user", "content": prompt}],
            "tools": [
                {
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": self.params.get("max_uses", 3),
                    "user_location": {
                        "type": "approximate",
                        "city": market.city,
                        "region": market.region,
                        "country": market.country,
                        "timezone": market.timezone,
                    },
                }
            ],
        }
        headers = {
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        }
        resp, err, ms = self.post(URL, headers=headers, json=body)
        if err:
            return err
        return self.parse(resp.json(), resp.status_code, ms)

    def parse(self, data: dict, http_status: int = 200, latency_ms: int = 0) -> RawResult:
        if data.get("type") == "error":
            msg = (data.get("error") or {}).get("message", "unknown error")
            return error_result(msg[:300], retryable=False, http_status=http_status, raw=data)
        texts: list[str] = []
        cited: list[Citation] = []
        consulted: list[Citation] = []
        search_errors: list[str] = []
        ok_results = 0
        for block in data.get("content", []):
            kind = block.get("type")
            if kind == "text":
                texts.append(block.get("text", ""))
                for cit in block.get("citations") or []:
                    if cit.get("type") == "web_search_result_location" and cit.get("url"):
                        cited.append(Citation(cit["url"], cit.get("title"), kind="cited"))
            elif kind == "web_search_tool_result":
                content = block.get("content")
                if isinstance(content, dict) and content.get("type") == "web_search_tool_result_error":
                    search_errors.append(content.get("error_code", "unknown"))
                elif isinstance(content, list):
                    ok_results += 1
                    for r in content:
                        if r.get("url"):
                            consulted.append(Citation(r["url"], r.get("title"), kind="consulted"))
        # A search error arrives inside an HTTP 200. Do not score it as "not mentioned".
        if search_errors and ok_results == 0:
            retry = any(e in RETRYABLE_SEARCH_ERRORS for e in search_errors)
            return error_result(
                "web_search error: " + ",".join(search_errors),
                retryable=retry,
                http_status=http_status,
                raw=data,
                latency_ms=latency_ms,
            )
        cited_urls = {c.url for c in cited}
        extra = [c for c in consulted if c.url not in cited_urls]
        usage = data.get("usage") or {}
        tin, tout = usage.get("input_tokens"), usage.get("output_tokens")
        searches = (usage.get("server_tool_use") or {}).get("web_search_requests", 0)
        cost = (
            (tin or 0) * self.params.get("price_in", 0.10) / 1e6
            + (tout or 0) * self.params.get("price_out", 0.50) / 1e6
            + searches * SEARCH_USD
        )
        return RawResult(
            status="ok",
            answer_text="\n".join(texts),
            citations=dedupe_citations(cited + extra),
            raw=data,
            http_status=http_status,
            latency_ms=latency_ms,
            tokens_in=tin,
            tokens_out=tout,
            searches=searches,
            cost_usd=cost,
        )
