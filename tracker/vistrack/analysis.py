"""Turn stored runs into the numbers the report shows."""

from __future__ import annotations

import math
import re
import sqlite3
from collections import defaultdict

from .config import Config
from .names import name_overlap
from .stats import cluster_bootstrap, mean_pairwise_jaccard, wilson

DIRECTORY_DOMAINS = {
    "yelp.com",
    "healthgrades.com",
    "zocdoc.com",
    "webmd.com",
    "lantern.llc",
    "birdeye.com",
    "google.com",
    "facebook.com",
    "reddit.com",
    "rankmydentist.com",
    "yellowpages.com",
    "mapquest.com",
    "ada.org",
    "dentaly.org",
    "newmouth.com",
    "instagram.com",
}


_EMPHASIS = re.compile(r"\*\*([^*\n]{3,60})\*\*|\[([^\]\n]{3,60})\]\(https?://[^)]*\)")
_STOP = {
    "source",
    "sources",
    "best",
    "tip",
    "note",
    "bottom line",
    "quick take",
    "short answer",
    "pricing",
    "insurance",
    "hours",
    "address",
    "phone",
    "website",
    "reviews",
    "services",
    "emergency",
    "cosmetic",
    "my pick",
    "top pick",
    "also consider",
    "good options",
    "other options",
    "more",
    "link",
    "maps",
}
_NOT_NAME = re.compile(
    r"[:?!]$|\$|\bstars?\b|\breviews?\b|\bgoogle maps\b|\bhealthgrades\b|\byelp\b|\bwebmd\b|\bzocdoc\b", re.I
)


def heuristic_names(text: str, brands) -> set[str]:
    """Crude: bold or link-text phrases that look like business names and are not tracked brands.

    Only a guide to who else is named; no LLM judge ran, so expect noise.
    """
    from .extract import find_mentions

    out: set[str] = set()
    for m in _EMPHASIS.finditer(text):
        name = (m.group(1) or m.group(2)).strip().strip("-–—*_ ")
        words = name.split()
        if not (2 <= len(words) <= 6) or name.lower() in _STOP or _NOT_NAME.search(name):
            continue
        if name[0].islower() or find_mentions(name, brands):
            continue
        out.add(name)
    return out


def _both(conn: sqlite3.Connection, run_id: int, brand_id: str) -> bool:
    row = conn.execute(
        "SELECT matched_by FROM mention WHERE run_id = ? AND brand_id = ?", (run_id, brand_id)
    ).fetchone()
    return bool(row) and row["matched_by"] == "both"


def _category(domain: str, tracked: bool) -> str:
    if tracked:
        return "tracked clinic site"
    base = ".".join(domain.split(".")[-2:])
    return "directory / review / social" if base in DIRECTORY_DOMAINS or domain in DIRECTORY_DOMAINS else "other"


def build(conn: sqlite3.Connection, cfg: Config, batch: str) -> dict:
    runs = conn.execute("SELECT * FROM run WHERE batch = ? ORDER BY engine, prompt_id, rep_index", (batch,)).fetchall()
    ok_cells = {(r["prompt_id"], r["engine"], r["rep_index"]) for r in runs if r["status"] == "ok"}
    # an error that a later retry/resume fixed is not an error of the batch any more
    runs = [r for r in runs if r["status"] == "ok" or (r["prompt_id"], r["engine"], r["rep_index"]) not in ok_cells]
    mentions: dict[int, dict[str, tuple[int | None, int]]] = defaultdict(dict)  # regex layer (primary rate)
    judge_only: dict[int, set[str]] = defaultdict(set)  # named by the LLM judge, missed by regex
    for r in conn.execute(
        "SELECT m.run_id, m.brand_id, m.position, m.negative, m.matched_by FROM mention m "
        "JOIN run ON run.id = m.run_id WHERE run.batch = ?",
        (batch,),
    ):
        if r["matched_by"] == "judge":
            judge_only[r["run_id"]].add(r["brand_id"])
        else:
            mentions[r["run_id"]][r["brand_id"]] = (r["position"], r["negative"])
    judged_runs = {
        r["run_id"]
        for r in conn.execute(
            "SELECT j.run_id FROM judge_verdict j JOIN run ON run.id = j.run_id WHERE run.batch = ?", (batch,)
        )
    }
    cites: dict[int, list[tuple[str, str | None]]] = defaultdict(list)
    for r in conn.execute(
        "SELECT c.run_id, c.domain, c.brand_id FROM citation c JOIN run ON run.id = c.run_id "
        "WHERE run.batch = ? AND c.kind = 'cited'",
        (batch,),
    ):
        cites[r["run_id"]].append((r["domain"], r["brand_id"]))

    engines = sorted({r["engine"] for r in runs}, key=lambda e: list(_ORDER).index(e) if e in _ORDER else 99)
    brand_ids = [b.id for b in cfg.brands]
    prompt_ids = [p.id for p in cfg.prompts]
    meta = {
        "is_mock": any(r["is_mock"] for r in runs),
        "batch": batch,
        "n_runs": len(runs),
        "first_run": min((r["executed_at"] for r in runs), default=""),
        "last_run": max((r["executed_at"] for r in runs), default=""),
        "models": {e: sorted({r["model"] for r in runs if r["engine"] == e}) for e in engines},
        "location": runs[0]["location"] if runs else cfg.market.label,
    }

    eng_summary: dict[str, dict] = {}
    scored: dict[str, list] = {}  # runs that enter denominators
    for e in engines:
        rows = [r for r in runs if r["engine"] == e]
        ok = [r for r in rows if r["status"] == "ok"]
        scored[e] = [r for r in ok if r["answer_present"]]
        eng_summary[e] = {
            "reps": max((r["rep_index"] for r in rows), default=0),
            "attempted": len(rows),
            "errors": len(rows) - len(ok),
            "ok": len(ok),
            "no_answer": len(ok) - len(scored[e]),
            "scored": len(scored[e]),
            "cost": sum(r["cost_usd"] for r in rows),
            "mean_cost": (sum(r["cost_usd"] for r in rows) / len(rows)) if rows else 0.0,
        }

    # per brand x engine rates
    rates: dict[str, dict[str, dict]] = {b: {} for b in brand_ids}
    for b in brand_ids:
        for e in engines:
            rs = scored[e]
            n = len(rs)
            km = sum(1 for r in rs if b in mentions[r["id"]])
            kc = sum(1 for r in rs if any(bid == b for _, bid in cites[r["id"]]))
            pos = [mentions[r["id"]][b][0] for r in rs if b in mentions[r["id"]] and mentions[r["id"]][b][0]]
            neg = sum(1 for r in rs if b in mentions[r["id"]] and mentions[r["id"]][b][1])
            cells = []
            for p in prompt_ids:
                pr = [r for r in rs if r["prompt_id"] == p]
                cells.append((sum(1 for r in pr if b in mentions[r["id"]]), len(pr)))
            _mean_c, lo_c, hi_c = cluster_bootstrap(cells)
            lo, hi = wilson(km, n)
            clo, chi = wilson(kc, n)
            kj = sum(1 for r in rs if b in judge_only[r["id"]])  # extra mentions found only by the judge
            rates[b][e] = {
                "k_judge_extra": kj,
                "k_union": km + kj,
                "n_judged": sum(1 for r in rs if r["id"] in judged_runs),
                "k": km,
                "n": n,
                "rate": km / n if n else math.nan,
                "lo": lo,
                "hi": hi,
                "cluster_lo": lo_c,
                "cluster_hi": hi_c,
                "k_cited": kc,
                "cited_rate": kc / n if n else math.nan,
                "cited_lo": clo,
                "cited_hi": chi,
                "mean_position": sum(pos) / len(pos) if pos else math.nan,
                "negative": neg,
            }

    # share of voice among tracked brands (untracked businesses are invisible to the regex layer)
    sov: dict[str, dict[str, float]] = {}
    for e in engines:
        total = sum(rates[b][e]["k"] for b in brand_ids)
        sov[e] = {b: (rates[b][e]["k"] / total if total else math.nan) for b in brand_ids}

    # run-to-run variability
    variability: dict[str, dict] = {}
    examples: dict[str, dict] = {}
    for e in engines:
        jac, identical, cells_n, empty_cells = [], 0, 0, 0
        mixed, any_seen = 0, 0
        for p in prompt_ids:
            pr = [r for r in scored[e] if r["prompt_id"] == p]
            if len(pr) < 2:
                continue
            sets = [set(mentions[r["id"]]) for r in pr]
            if not any(sets):  # no tracked practice named in any repetition: nothing to compare
                empty_cells += 1
                continue
            jac.append(mean_pairwise_jaccard(sets))
            cells_n += 1
            identical += all(s == sets[0] for s in sets)
        for b in brand_ids:
            for p in prompt_ids:
                pr = [r for r in scored[e] if r["prompt_id"] == p]
                k = sum(1 for r in pr if b in mentions[r["id"]])
                if k >= 1:
                    any_seen += 1
                    mixed += k < len(pr)
        variability[e] = {
            "mean_jaccard": sum(jac) / len(jac) if jac else math.nan,
            "identical_cells": identical,
            "cells": cells_n,
            "empty_cells": empty_cells,
            "mixed": mixed,
            "seen": any_seen,
        }
        # the same question asked again: what each repetition named (first prompt with >= 3 reps)
        for p in prompt_ids:
            pr = [r for r in scored[e] if r["prompt_id"] == p]
            if len(pr) >= 3:
                examples[e] = {
                    "prompt": pr[0]["prompt_text"],
                    "reps": [
                        {"rep": r["rep_index"], "named": [b for b in brand_ids if b in mentions[r["id"]]]} for r in pr
                    ],
                }
                break

    # per-brand prompt x engine k/n grid
    heat: dict[str, list[dict]] = {}
    for b in brand_ids:
        grid = []
        for p in cfg.prompts:
            row = {"prompt": p.text, "cells": []}
            for e in engines:
                pr = [r for r in scored[e] if r["prompt_id"] == p.id]
                row["cells"].append({"k": sum(1 for r in pr if b in mentions[r["id"]]), "n": len(pr)})
            grid.append(row)
        heat[b] = grid

    # top cited domains
    tracked_domains = {d: b.id for b in cfg.brands for d in b.domains}
    per_domain: dict[str, dict] = {}
    total_scored = sum(len(v) for v in scored.values())
    for e in engines:
        for r in scored[e]:
            for dom in {d for d, _ in cites[r["id"]] if d}:
                entry = per_domain.setdefault(dom, {"domain": dom, "runs": 0, "by_engine": defaultdict(int)})
                entry["runs"] += 1
                entry["by_engine"][e] += 1
    top_domains = sorted(per_domain.values(), key=lambda d: -d["runs"])[:15]
    for d in top_domains:
        d["share"] = d["runs"] / total_scored if total_scored else math.nan
        d["category"] = _category(
            d["domain"], d["domain"] in tracked_domains or any(d["domain"].endswith("." + t) for t in tracked_domains)
        )
        d["by_engine"] = dict(d["by_engine"])

    judge_agree: dict[str, dict[str, int]] = {}
    for e in engines:
        jr = [r for r in scored[e] if r["id"] in judged_runs]
        both = sum(1 for r in jr for b in mentions[r["id"]] if _both(conn, r["id"], b))
        judge_agree[e] = {
            "runs_judged": len(jr),
            "both": both,
            "regex_only": sum(len(mentions[r["id"]]) for r in jr) - both,
            "judge_only": sum(len(judge_only[r["id"]]) for r in jr),
        }
    others = conn.execute(
        "SELECT name, COUNT(*) AS c FROM other_business ob JOIN run ON run.id = ob.run_id "
        "WHERE run.batch = ? GROUP BY name ORDER BY c DESC LIMIT 15",
        (batch,),
    ).fetchall()
    other_distinct = conn.execute(
        "SELECT COUNT(DISTINCT lower(name)) AS n FROM other_business ob JOIN run ON run.id = ob.run_id "
        "WHERE run.batch = ?",
        (batch,),
    ).fetchone()["n"]
    if not others:  # no LLM judge ran: fall back to a crude heuristic on emphasised names
        tracked_names = list(cfg.brands)
        counts: dict[str, int] = defaultdict(int)
        for e in engines:
            for r in scored[e]:
                for name in heuristic_names(r["answer_text"] or "", tracked_names):
                    counts[name] += 1
        others = [{"name": n, "c": c} for n, c in sorted(counts.items(), key=lambda kv: -kv[1])[:15]]
        other_distinct = len(counts)
        d_other_heuristic = True
    else:
        d_other_heuristic = False

    return {
        "meta": meta,
        "engines": engines,
        "engine_summary": eng_summary,
        "rates": rates,
        "sov": sov,
        "variability": variability,
        "examples": examples,
        "heat": heat,
        "top_domains": top_domains,
        "other_businesses": [(r["name"], r["c"]) for r in others],
        "other_heuristic": d_other_heuristic,
        "judge_agree": judge_agree,
        "other_hidden": False,
        "other_distinct": other_distinct,
        "name_overlap": name_overlap(conn, cfg, batch),
        "total_cost": sum(s["cost"] for s in eng_summary.values()),
    }


_ORDER = ("codex_cli", "claude_cli", "openai", "anthropic", "perplexity", "google_aio", "google_ai_mode")
