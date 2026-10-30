"""Engine adapter interface and shared helpers."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from ..config import Market

TIMEOUT = httpx.Timeout(120.0, connect=15.0)


@dataclass(frozen=True)
class Citation:
    url: str
    title: str | None = None
    rank: int = 0
    kind: str = "cited"  # cited = referenced in the answer; consulted = only in the search results


@dataclass
class RawResult:
    status: str = "ok"  # ok | error
    answer_text: str = ""
    citations: list[Citation] = field(default_factory=list)
    raw: Any = None
    answer_present: bool = True
    error: str | None = None
    retryable: bool = False
    http_status: int | None = None
    latency_ms: int = 0
    tokens_in: int | None = None
    tokens_out: int | None = None
    searches: int | None = None
    cost_usd: float = 0.0
    fatal: bool = False  # quota / auth failure: the runner stops the whole batch


def error_result(
    msg: str,
    *,
    retryable: bool,
    http_status: int | None = None,
    raw: Any = None,
    latency_ms: int = 0,
    fatal: bool = False,
) -> RawResult:
    return RawResult(
        status="error",
        error=msg,
        retryable=retryable,
        http_status=http_status,
        raw=raw,
        latency_ms=latency_ms,
        fatal=fatal,
    )


class Engine:
    """One search-enabled AI surface reached through an official API / SERP provider."""

    key = ""
    label = ""
    tool_version = ""
    env_vars: tuple[str, ...] = ()
    est_cost_upper = 0.0  # USD per call, upper end of the research-04 range
    default_model = ""
    serial = False  # True: one call at a time, with pause_seconds between calls (subscription CLIs)
    pause_seconds = 0.0

    def __init__(
        self,
        model: str | None = None,
        params: dict | None = None,
        client: httpx.Client | None = None,
        reps: int | None = None,
    ) -> None:
        self.model = model or self.default_model
        self.params = dict(params or {})
        self.client = client or httpx.Client(timeout=TIMEOUT)
        self.reps = reps  # per-engine repetitions; None = batch default

    def missing_env(self) -> list[str]:
        return [v for v in self.env_vars if not os.environ.get(v)]

    def available(self) -> bool:
        return not self.missing_env()

    def query(self, prompt: str, market: Market) -> RawResult:  # pragma: no cover - interface
        raise NotImplementedError

    def post(
        self, url: str, *, headers: dict | None = None, json: Any = None, auth: tuple[str, str] | None = None
    ) -> tuple[httpx.Response | None, RawResult | None, int]:
        """POST helper. Returns (response, error_result, latency_ms)."""
        t0 = time.monotonic()
        try:
            resp = self.client.post(url, headers=headers, json=json, auth=auth)
        except httpx.HTTPError as exc:
            ms = int((time.monotonic() - t0) * 1000)
            return None, error_result(f"{type(exc).__name__}: {exc}", retryable=True, latency_ms=ms), ms
        ms = int((time.monotonic() - t0) * 1000)
        if resp.status_code >= 400:
            retry = resp.status_code == 429 or resp.status_code >= 500
            return (
                resp,
                error_result(
                    f"HTTP {resp.status_code}: {resp.text[:300]}",
                    retryable=retry,
                    http_status=resp.status_code,
                    latency_ms=ms,
                ),
                ms,
            )
        return resp, None, ms


def dedupe_citations(cites: list[Citation]) -> list[Citation]:
    seen: set[str] = set()
    out = []
    for c in cites:
        if c.url in seen:
            continue
        seen.add(c.url)
        out.append(Citation(c.url, c.title, len(out) + 1, c.kind))
    return out
