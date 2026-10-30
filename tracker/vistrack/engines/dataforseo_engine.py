"""Google AI Overviews and AI Mode through DataForSEO SERP APIs (third-party provider)."""

from __future__ import annotations

import os

from ..config import Market
from .base import Citation, Engine, RawResult, dedupe_citations, error_result

BASE = "https://api.dataforseo.com/v3/serp/google"
OK_CODE = 20000


class _DataForSeoEngine(Engine):
    env_vars = ("DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD")
    path = ""
    default_model = "dataforseo-serp"

    def task_body(self, prompt: str, market: Market) -> dict:
        return {
            "keyword": prompt,
            "location_name": market.dfs_location_name,
            "language_code": "en",
            "device": "desktop",
        }

    def query(self, prompt: str, market: Market) -> RawResult:
        auth = (os.environ["DATAFORSEO_LOGIN"], os.environ["DATAFORSEO_PASSWORD"])
        resp, err, ms = self.post(f"{BASE}/{self.path}", json=[self.task_body(prompt, market)], auth=auth)
        if err:
            return err
        return self.parse(resp.json(), resp.status_code, ms)

    def parse(self, data: dict, http_status: int = 200, latency_ms: int = 0) -> RawResult:
        if data.get("status_code") != OK_CODE:
            return error_result(
                f"DataForSEO {data.get('status_code')}: {data.get('status_message')}",
                retryable=False,
                http_status=http_status,
                raw=data,
            )
        tasks = data.get("tasks") or []
        task = tasks[0] if tasks else {}
        if task.get("status_code") != OK_CODE:
            return error_result(
                f"task {task.get('status_code')}: {task.get('status_message')}",
                retryable=task.get("status_code", 0) >= 50000,
                http_status=http_status,
                raw=data,
            )
        result = (task.get("result") or [{}])[0] or {}
        overview = next((i for i in result.get("items") or [] if i.get("type") == "ai_overview"), None)
        cost = float(data.get("cost") or 0)
        if overview is None:  # valid response, no AI answer shown: not an error, not a mention
            return RawResult(
                status="ok",
                answer_text="",
                answer_present=False,
                raw=data,
                http_status=http_status,
                latency_ms=latency_ms,
                cost_usd=cost,
            )
        text = overview.get("markdown") or "\n".join(
            el.get("text", "") for el in overview.get("items") or [] if el.get("text")
        )
        refs = list(overview.get("references") or [])
        for el in overview.get("items") or []:
            refs.extend(el.get("references") or [])
        cites = [Citation(r["url"], r.get("title"), kind="cited") for r in refs if r.get("url")]
        return RawResult(
            status="ok",
            answer_text=text,
            citations=dedupe_citations(cites),
            raw=data,
            http_status=http_status,
            latency_ms=latency_ms,
            cost_usd=cost,
        )


class GoogleAioEngine(_DataForSeoEngine):
    key = "google_aio"
    label = "Google AI Overviews (DataForSEO)"
    tool_version = "serp/google/organic/live/advanced+load_async_ai_overview"
    est_cost_upper = 0.004
    path = "organic/live/advanced"

    def task_body(self, prompt: str, market: Market) -> dict:
        return {**super().task_body(prompt, market), "load_async_ai_overview": True}


class GoogleAiModeEngine(_DataForSeoEngine):
    key = "google_ai_mode"
    label = "Google AI Mode (DataForSEO)"
    tool_version = "serp/google/ai_mode/live/advanced"
    est_cost_upper = 0.004
    path = "ai_mode/live/advanced"
