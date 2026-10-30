"""Recompute mentions and citation ownership from stored answers (no new queries).

Use after fixing a brand alias or domain in the config. Stored LLM-judge verdicts are kept and
re-reconciled against the new regex result, so the judge does not have to run again.
"""

from __future__ import annotations

import json
import sqlite3

from .config import Config
from .extract import extract
from .judge import JudgeVerdict, reconcile


def reextract(conn: sqlite3.Connection, cfg: Config, batch: str) -> int:
    runs = conn.execute(
        "SELECT id, answer_text FROM run WHERE batch = ? AND status = 'ok' AND answer_present = 1", (batch,)
    ).fetchall()
    for r in runs:
        run_id = r["id"]
        urls = [
            c["url"] for c in conn.execute("SELECT url FROM citation WHERE run_id = ? AND kind = 'cited'", (run_id,))
        ]
        ex = extract(r["answer_text"] or "", urls, cfg.brands)
        by_brand = {m.brand_id: m for m in ex.mentions}
        how = dict.fromkeys(by_brand, "regex")
        verdict_row = conn.execute("SELECT verdict_json FROM judge_verdict WHERE run_id = ?", (run_id,)).fetchone()
        judge_rank: dict[str, int] = {}
        if verdict_row:
            v = json.loads(verdict_row["verdict_json"])
            valid = {b.id for b in cfg.brands}
            judge_rank = {b: rk for b, rk in v["tracked"].items() if b in valid}
            how = reconcile(set(by_brand), JudgeVerdict(judge_rank, v.get("others", [])))
        conn.execute("DELETE FROM mention WHERE run_id = ?", (run_id,))
        conn.executemany(
            "INSERT INTO mention (run_id, brand_id, first_offset, position, matched_by, negative) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    run_id,
                    b,
                    by_brand[b].offset if b in by_brand else None,
                    by_brand[b].position if b in by_brand else (judge_rank.get(b) or None),
                    h,
                    int(by_brand[b].negative) if b in by_brand else 0,
                )
                for b, h in how.items()
            ],
        )
        for url, _, bid in ex.citations:
            conn.execute(
                "UPDATE citation SET brand_id = ? WHERE run_id = ? AND url = ? AND kind = 'cited'", (bid, run_id, url)
            )
    conn.commit()
    return len(runs)
