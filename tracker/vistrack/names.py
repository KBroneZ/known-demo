"""Run-to-run overlap of ALL businesses named in answers (tracked practices plus the judge's other names).

This is the headline "one answer is not a result" number. It needs LLM-judge verdicts (`vistrack judge`);
without them only the 8 tracked practices are visible and most answers name none of them.
"""

from __future__ import annotations

import math
import re
import sqlite3
from collections import Counter, defaultdict

from .config import Config
from .stats import pair_jaccards


def norm_name(name: str) -> str:
    """Compare business names loosely: lowercase, no punctuation, no leading 'dr' / trailing 'dds'."""
    s = re.sub(r"[^a-z0-9 ]+", " ", name.casefold())
    s = re.sub(r"^(dr|the)\s+", "", s.strip())
    s = re.sub(r"\s+(dds|dmd|pllc|llc|pa)$", "", s)
    return re.sub(r"\s+", " ", s).strip()


def name_overlap(conn: sqlite3.Connection, cfg: Config, batch: str) -> dict[str, dict]:
    brand_name = {b.id: norm_name(b.name) for b in cfg.brands}
    runs = conn.execute(
        "SELECT r.id, r.engine, r.prompt_id FROM run r JOIN judge_verdict j ON j.run_id = r.id "
        "WHERE r.batch = ? AND r.status = 'ok' AND r.answer_present = 1",
        (batch,),
    ).fetchall()
    names: dict[int, set[str]] = defaultdict(set)
    for r in conn.execute(
        "SELECT m.run_id, m.brand_id FROM mention m JOIN run ON run.id = m.run_id WHERE run.batch = ?", (batch,)
    ):
        names[r["run_id"]].add(brand_name[r["brand_id"]])
    for r in conn.execute(
        "SELECT o.run_id, o.name FROM other_business o JOIN run ON run.id = o.run_id WHERE run.batch = ?", (batch,)
    ):
        names[r["run_id"]].add(norm_name(r["name"]))
    out: dict[str, dict] = {}
    for engine in sorted({r["engine"] for r in runs}):
        by_prompt: dict[str, list[set[str]]] = defaultdict(list)
        for r in runs:
            if r["engine"] == engine:
                by_prompt[r["prompt_id"]].append(names[r["id"]])
        pooled: list[float] = []
        per_prompt: list[float] = []
        every = one = pairs = 0
        distinct: set[str] = set()
        for sets in by_prompt.values():
            js = pair_jaccards(sets)
            pooled += js
            if js:
                per_prompt.append(sum(js) / len(js))
            counts = Counter(n for s in sets for n in s)
            distinct |= set(counts)
            pairs += len(counts)
            if len(sets) >= 2:
                every += sum(1 for v in counts.values() if v == len(sets))
                one += sum(1 for v in counts.values() if v == 1)
        sizes = [len(s) for sets in by_prompt.values() for s in sets]
        out[engine] = {
            "answers": len(sizes),
            "prompts": len(by_prompt),
            "reps": sorted({len(s) for s in by_prompt.values()}),
            "mean_names_per_answer": sum(sizes) / len(sizes) if sizes else math.nan,
            "mean_jaccard": sum(pooled) / len(pooled) if pooled else math.nan,
            "per_prompt_min": min(per_prompt) if per_prompt else math.nan,
            "per_prompt_max": max(per_prompt) if per_prompt else math.nan,
            "distinct_names": len(distinct),
            "name_prompt_pairs": pairs,
            "pairs_in_every_rep": every,
            "pairs_in_one_rep": one,
        }
    return out
