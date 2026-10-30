"""Perplexity Agent API + web_search tool (Sonar Chat Completions is unsupported since 2026-09-27)."""

from __future__ import annotations

import os
import re

from ..config import Market
from .base import Citation, Engine, RawResult, dedupe_citations, error_result

URL = "https://api.perplexity.ai/v1/agent"
SEARCH_USD = 0.0025
# Only asks for [n] markers so we can tell cited sources from merely retrieved ones.
INSTRUCTIONS = "Mark each source you rely on with its bracketed number, like [1]."


class PerplexityEngine(Engine):
    key = "perplexity"
    label = "Perplexity (Agent API)"
    tool_version = "agent/web_search"
    env_vars = ("PERPLEXITY_API_KEY",)
    est_cost_upper = 0.010
    default_model = "perplexity/sonar"  # per research 04; verify against docs.perplexity.ai/docs/agent-api/models

    def query(self, prompt: str, market: Market) -> RawResult:
        body = {
            "model": self.model,
            "input": prompt,
            "instructions": INSTRUCTIONS,
            "tools": [
                {
                    "type": "web_search",
                    "user_location": {
                        "country": market.country,
                        "region": market.region,
                        "city": market.city,
                    },
                }
            ],
        }
        headers = {"Authorization": f"Bearer {os.environ['PERPLEXITY_API_KEY']}"}
        resp, err, ms = self.post(URL, headers=headers, json=body)
        if err:
            return err
        return self.parse(resp.json(), resp.status_code, ms)

    def parse(self, data: dict, http_status: int = 200, latency_ms: int = 0) -> RawResult:
        if data.get("error"):
            return error_result(str(data["error"])[:300], retryable=False, http_status=http_status, raw=data)
        results: list[dict] = []
        texts: list[str] = []
        for item in data.get("output", []) or []:
            if item.get("type") == "search_results":
                results.extend(item.get("results", []))
            elif item.get("type") == "message":
                for part in item.get("content", []):
                    if part.get("type") == "output_text":
                        texts.append(part.get("text", ""))
        if not results:  # docs show a top-level `results` in some examples; accept both
            results = data.get("results", []) or []
        answer = "\n".join(texts)
        referenced = {int(n) for n in re.findall(r"\[(\d+)\]", answer)}
        cites = []
        for idx, r in enumerate(results, start=1):
            rid = r.get("id", idx)
            try:
                rid = int(rid)
            except (TypeError, ValueError):
                rid = idx
            if r.get("url"):
                kind = "cited" if rid in referenced else "consulted"
                cites.append(Citation(r["url"], r.get("title"), kind=kind))
        usage = data.get("usage") or {}
        tin, tout = usage.get("input_tokens"), usage.get("output_tokens")
        searches = (((usage.get("tool_calls_details") or {}).get("search_web")) or {}).get("invocation", 0)
        cost = (
            (tin or 0) * self.params.get("price_in", 0.25) / 1e6
            + (tout or 0) * self.params.get("price_out", 2.50) / 1e6
            + searches * SEARCH_USD
        )
        return RawResult(
            status="ok",
            answer_text=answer,
            citations=dedupe_citations(cites),
            raw=data,
            http_status=http_status,
            latency_ms=latency_ms,
            tokens_in=tin,
            tokens_out=tout,
            searches=searches,
            cost_usd=cost,
        )
