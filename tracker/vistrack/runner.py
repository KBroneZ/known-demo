"""Batch runner: schedule, call engines, retry, store raw JSON + extraction, enforce the budget."""

from __future__ import annotations

import hashlib
import json
import random
import sqlite3
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import db
from .config import Config, Prompt
from .cost import check_plan, estimate
from .engines.base import Engine, RawResult
from .extract import extract
from .judge import JudgeVerdict, reconcile

MAX_ATTEMPTS = 3
CHUNK = 8


@dataclass
class RunSummary:
    batch: str
    planned: int = 0
    skipped_done: int = 0
    ok: int = 0
    errors: int = 0
    spent_usd: float = 0.0
    stopped_early: bool = False
    notes: list[str] = field(default_factory=list)


def _call_with_retry(engine: Engine, prompt: str, cfg: Config, backoff: float) -> RawResult:
    result = RawResult(status="error", error="not run")
    for attempt in range(MAX_ATTEMPTS):
        result = engine.query(prompt, cfg.market)
        if result.status == "ok" or not result.retryable:
            return result
        if attempt < MAX_ATTEMPTS - 1:
            time.sleep(backoff * (2**attempt))
    return result


def _store_raw(raw_dir: Path, raw: object) -> tuple[str, str]:
    blob = json.dumps(raw, ensure_ascii=False, sort_keys=True, indent=1).encode("utf-8")
    digest = hashlib.sha256(blob).hexdigest()
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{digest}.json"
    if not path.exists():
        path.write_bytes(blob)
    return str(path), digest


def run_batch(
    cfg: Config,
    engines: list[Engine],
    conn: sqlite3.Connection,
    *,
    batch: str,
    reps: int,
    budget_usd: float,
    raw_dir: Path,
    is_mock: bool = False,
    seed: int = 0,
    backoff: float = 2.0,
    workers: int = 4,
    judge: Callable[[str], JudgeVerdict] | None = None,
    log: Callable[[str], None] = print,
) -> RunSummary:
    summary = RunSummary(batch)
    est = estimate(cfg, engines, reps)
    check_plan(est, budget_usd)  # raises before any money is spent
    log(f"planned {est.calls} calls, upper-bound ${est.upper_usd:.2f} (budget ${budget_usd:.2f})")

    done = db.done_cells(conn, batch)
    by_key = {e.key: e for e in engines}
    tasks: list[tuple[Prompt, str, int]] = [
        (p, e.key, r) for p in cfg.prompts for e in engines for r in range(1, (e.reps or reps) + 1)
    ]
    summary.planned = len(tasks)
    todo = [t for t in tasks if (t[0].id, t[1], t[2]) not in done]
    summary.skipped_done = len(tasks) - len(todo)
    random.Random(seed).shuffle(todo)  # spread engines/prompts so a budget stop is not biased to one cell
    spent = db.batch_cost(conn, batch)
    max_call_cost = max((e.est_cost_upper for e in engines), default=0.0)

    serial = [t for t in todo if by_key[t[1]].serial]
    todo = [t for t in todo if not by_key[t[1]].serial]
    for n, (p, key, rep) in enumerate(serial, start=1):  # subscription CLIs: one at a time, with pauses
        engine = by_key[key]
        result = _call_with_retry(engine, p.text, cfg, backoff)
        _store_result(cfg, conn, engine, p, rep, result, batch, is_mock, raw_dir, judge)
        conn.commit()
        summary.ok += result.status == "ok"
        summary.errors += result.status != "ok"
        log(
            f"[{n}/{len(serial)}] {key} {p.id} rep{rep}: {result.status}"
            + (f" ({result.error[:120]})" if result.error else "")
        )
        if result.fatal:
            summary.stopped_early = True
            summary.notes.append(f"stopped on fatal {key} error (quota/auth): {result.error}")
            log(summary.notes[-1])
            summary.spent_usd = db.batch_cost(conn, batch)
            return summary
        if n < len(serial) and engine.pause_seconds:
            time.sleep(engine.pause_seconds)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i in range(0, len(todo), CHUNK):
            if spent + CHUNK * max_call_cost > budget_usd and not is_mock:
                summary.stopped_early = True
                summary.notes.append(f"stopped before call {i}: next chunk could exceed ${budget_usd:.2f}")
                log(summary.notes[-1])
                break
            futures = {
                pool.submit(_call_with_retry, by_key[key], p.text, cfg, backoff): (p, key, rep)
                for p, key, rep in todo[i : i + CHUNK]
            }
            for fut in as_completed(futures):
                p, key, rep = futures[fut]
                try:
                    result = fut.result()
                except Exception as exc:  # adapter bug: record, never crash the batch
                    result = RawResult(status="error", error=f"{type(exc).__name__}: {exc}")
                _store_result(cfg, conn, by_key[key], p, rep, result, batch, is_mock, raw_dir, judge)
                spent += result.cost_usd
                if result.status == "ok":
                    summary.ok += 1
                else:
                    summary.errors += 1
            conn.commit()
    summary.spent_usd = db.batch_cost(conn, batch)
    return summary


def _store_result(
    cfg: Config,
    conn: sqlite3.Connection,
    engine: Engine,
    prompt: Prompt,
    rep: int,
    result: RawResult,
    batch: str,
    is_mock: bool,
    raw_dir: Path,
    judge: Callable[[str], JudgeVerdict] | None,
    *,
    executed_at: str | None = None,
    location: str | None = None,
) -> None:
    raw_path, digest = (None, None)
    if result.raw is not None:
        raw_path, digest = _store_raw(raw_dir, result.raw)
    run_id = db.insert_run(
        conn,
        {
            "batch": batch,
            "is_mock": int(is_mock),
            "prompt_id": prompt.id,
            "prompt_text": prompt.text,
            "engine": engine.key,
            "model": engine.model,
            "tool_version": engine.tool_version,
            "location": location or cfg.market.label,
            "rep_index": rep,
            "executed_at": executed_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": result.status,
            "answer_present": int(result.answer_present),
            "error": result.error,
            "http_status": result.http_status,
            "latency_ms": result.latency_ms,
            "cost_usd": result.cost_usd,
            "tokens_in": result.tokens_in,
            "tokens_out": result.tokens_out,
            "searches": result.searches,
            "raw_path": raw_path,
            "raw_sha256": digest,
            "answer_text": result.answer_text,
        },
    )
    if result.status != "ok" or not result.answer_present:
        return
    cited_urls = [c.url for c in result.citations if c.kind == "cited"]
    ex = extract(result.answer_text, cited_urls, cfg.brands)
    matched = {m.brand_id: "regex" for m in ex.mentions}
    others: list[str] = []
    if judge is not None:
        try:
            verdict = judge(result.answer_text)
            matched = reconcile(ex.mentioned_ids, verdict)
            others = verdict.others
        except Exception as exc:  # judge failure must not drop the run
            conn.execute("UPDATE run SET error = ? WHERE id = ?", (f"judge failed: {exc}", run_id))
    by_brand = {m.brand_id: m for m in ex.mentions}
    mention_rows = [
        {
            "brand_id": bid,
            "first_offset": by_brand[bid].offset if bid in by_brand else None,
            "position": by_brand[bid].position if bid in by_brand else None,
            "matched_by": how,
            "negative": int(by_brand[bid].negative) if bid in by_brand else 0,
        }
        for bid, how in matched.items()
    ]
    db.insert_mentions(conn, run_id, mention_rows)
    brand_of = {url: bid for url, _, bid in ex.citations}
    cite_rows = [
        {
            "rank": c.rank,
            "kind": c.kind,
            "url": c.url,
            "domain": _domain(c.url),
            "title": c.title,
            "brand_id": brand_of.get(c.url) if c.kind == "cited" else None,
        }
        for c in result.citations
    ]
    db.insert_citations(conn, run_id, cite_rows)
    if others:
        db.insert_other_businesses(conn, run_id, others)


def _domain(url: str) -> str:
    from .extract import domain_of

    return domain_of(url)
