"""Validate the regex extractor against a hand-labelled gold set."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from .extract import Brand, extract
from .stats import wilson


def load_gold(path: str | Path) -> list[dict]:
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else float("nan")
    r = tp / (tp + fn) if tp + fn else float("nan")
    f1 = 2 * p * r / (p + r) if tp and p + r else float("nan")
    return {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r, "f1": f1}


def evaluate_real(gold: Sequence[dict], brands: Sequence[Brand], verdicts: dict[str, set[str]]) -> dict:
    """Mention precision/recall on labelled real answers: regex alone, judge alone, either, both.

    verdicts maps gold id -> brand ids the LLM judge named (missing id = judge not run on it).
    """
    keys = ("regex", "judge", "either", "both")
    counts = {k: [0, 0, 0] for k in keys}
    errors = []
    judged = 0
    for item in gold:
        truth = set(item["mentioned"])
        regex = extract(item["answer"], item.get("cited_urls", []), brands).mentioned_ids
        have_judge = item["id"] in verdicts
        judged += have_judge
        judge = verdicts.get(item["id"], set())
        preds = {"regex": regex, "judge": judge, "either": regex | judge, "both": regex & judge}
        for k in keys:
            if k != "regex" and not have_judge:
                continue
            counts[k][0] += len(preds[k] & truth)
            counts[k][1] += len(preds[k] - truth)
            counts[k][2] += len(truth - preds[k])
            if (preds[k] ^ truth) and k in ("regex", "judge"):
                errors.append(
                    {
                        "id": item["id"],
                        "who": k,
                        "false_positive": sorted(preds[k] - truth),
                        "false_negative": sorted(truth - preds[k]),
                        "note": item.get("note", ""),
                    }
                )
    return {
        "n_items": len(gold),
        "n_judged": judged,
        "n_items_with_a_tracked_brand": sum(1 for i in gold if i["mentioned"]),
        "n_true_mentions": sum(len(i["mentioned"]) for i in gold),
        "labeled_by": sorted({i.get("labeled_by", "") for i in gold}),
        **{k: _prf(*counts[k]) for k in keys},
        "errors": errors,
    }


def evaluate(gold: Sequence[dict], brands: Sequence[Brand]) -> dict:
    """Micro precision/recall over (answer, brand) pairs for mentions and citations."""
    counts = {"mentioned": [0, 0, 0], "cited": [0, 0, 0]}
    errors = []
    exact = 0
    for item in gold:
        ex = extract(item["answer"], item.get("cited_urls", []), brands)
        pred = {"mentioned": ex.mentioned_ids, "cited": ex.cited_ids}
        item_ok = True
        for field in counts:
            truth = set(item[field])
            tp = len(pred[field] & truth)
            fp = len(pred[field] - truth)
            fn = len(truth - pred[field])
            counts[field][0] += tp
            counts[field][1] += fp
            counts[field][2] += fn
            if fp or fn:
                item_ok = False
                errors.append(
                    {
                        "id": item["id"],
                        "field": field,
                        "note": item.get("note", ""),
                        "false_positive": sorted(pred[field] - truth),
                        "false_negative": sorted(truth - pred[field]),
                    }
                )
        exact += item_ok
    n = len(gold)
    lo, hi = wilson(exact, n)
    return {
        "n_items": n,
        "mentioned": _prf(*counts["mentioned"]),
        "cited": _prf(*counts["cited"]),
        "item_exact_match": {"k": exact, "n": n, "rate": exact / n if n else float("nan"), "wilson95": [lo, hi]},
        "errors": errors,
    }
