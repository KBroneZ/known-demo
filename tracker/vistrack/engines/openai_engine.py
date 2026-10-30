"""OpenAI Responses API + web_search tool (proxy for ChatGPT search)."""

from __future__ import annotations

import os

from ..config import Market
from .base import Citation, Engine, RawResult, dedupe_citations, error_result

URL = "https://api.openai.com/v1/responses"
SEARCH_USD = 0.010  # per web_search call, research 04 (2026-10-30)


class OpenAIEngine(Engine):
    key = "openai"
    label = "ChatGPT (OpenAI API)"
    tool_version = "responses/web_search"
    env_vars = ("OPENAI_API_KEY",)
    est_cost_upper = 0.036
    default_model = "gpt-5.4-mini"  # model id from research 04; verify before the real run

    def query(self, prompt: str, market: Market) -> RawResult:
        body = {
            "model": self.model,
            "input": prompt,
            "tools": [
                {
                    "type": "web_search",
                    "search_context_size": self.params.get("search_context_size", "medium"),
                    "user_location": {
                        "type": "approximate",
                        "country": market.country,
                        "city": market.city,
                        "region": market.region,
                        "timezone": market.timezone,
                    },
                }
            ],
            "include": ["web_search_call.action.sources"],
        }
        headers = {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"}
        resp, err, ms = self.post(URL, headers=headers, json=body)
        if err:
            return err
        return self.parse(resp.json(), resp.status_code, ms)

    def parse(self, data: dict, http_status: int = 200, latency_ms: int = 0) -> RawResult:
        if data.get("error"):
            return error_result(str(data["error"])[:300], retryable=False, http_status=http_status, raw=data)
        texts: list[str] = []
        cited: list[Citation] = []
        consulted: list[Citation] = []
        searches = 0
        for item in data.get("output", []):
            kind = item.get("type")
            if kind == "web_search_call":
                searches += 1
                for src in (item.get("action") or {}).get("sources") or []:
                    if src.get("url"):
                        consulted.append(Citation(src["url"], src.get("title"), kind="consulted"))
            elif kind == "message":
                for part in item.get("content", []):
                    if part.get("type") != "output_text":
                        continue
                    texts.append(part.get("text", ""))
                    for ann in part.get("annotations", []):
                        if ann.get("type") == "url_citation" and ann.get("url"):
                            cited.append(Citation(ann["url"], ann.get("title"), kind="cited"))
        cited_urls = {c.url for c in cited}
        extra = [c for c in consulted if c.url not in cited_urls]
        usage = data.get("usage") or {}
        tin, tout = usage.get("input_tokens"), usage.get("output_tokens")
        cost = (
            (tin or 0) * self.params.get("price_in", 0.75) / 1e6
            + (tout or 0) * self.params.get("price_out", 4.50) / 1e6
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
