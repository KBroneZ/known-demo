#!/usr/bin/env python3
"""Score the gate against the seeded errors: recall, precision, false positives on clean posts.

    python evaluate.py              # offline (link results come from fixtures/link-cache.json)
    python evaluate.py --online     # live HEAD requests
    python evaluate.py --with-llm --model-dir reports/model-sonnet   # also score a model run

A seeded error counts as detected when a finding of one of its accepted rules lands on the
line that holds the injected text (same line, +/-0). Findings of severity block/warn that do
not match a seeded error are false positives; `info` findings are not counted.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

from qa_gate import links
from qa_gate.cli import DEFAULT_CACHE, DEFAULT_CLINIC, DEFAULT_REPORTS, QA_ROOT
from qa_gate.gate import check_file
from qa_gate.loader import load_clinic

FIXTURES = QA_ROOT / "fixtures"
COUNTED = ("block", "warn")
CATEGORY_RULES = {  # held-out errors name a category, not a rule: map it to the rules that count as a hit
    "nap": [
        "nap_phone_mismatch",
        "nap_address_mismatch",
        "nap_name_variant",
        "hours_mismatch",
        "dentist_not_in_roster",
        "price_not_in_ficha",
        "insurance_not_in_ficha",
        "service_not_in_ficha",
    ],
    "ai_phrase": ["ai_phrase"],
    "broken_link": ["link_broken", "link_broken_internal"],
    "unsourced_stat": ["unsourced_stat"],
    "prohibited_promise": ["prohibited_promise"],
    "schema": ["schema_mismatch", "schema_invalid", "schema_invalid_json"],
    "medical_false": ["medical_myth"],
    "testimonial": ["fake_testimonial"],
    "superlative": ["unsupported_superlative"],
    "chatbot": ["chatbot_residue", "placeholder"],
    # heldout3 (categories named by its ChatGPT author); mapping fixed before the set was scored.
    # '*' = any block/warn finding on the line counts, because no single rule is "the" answer.
    "medical-misinformation": ["medical_myth"],
    "outcome-guarantee": ["prohibited_promise"],
    "unsupported-clinic-claim": ["*"],
    "price-not-on-sheet": ["price_not_in_ficha"],
    "insurance-not-accepted": ["insurance_not_in_ficha"],
    "wrong-author": ["dentist_not_in_roster"],
    "invented-statistic": ["unsourced_stat"],
    "hours-error": ["hours_mismatch"],
    "internal-link-missing-page": ["link_broken_internal"],
    # travel blind set: the category vocabulary given to its author, mapped before the set was scored.
    # Categories that need world knowledge map to no rule on purpose (rules-only recall counts them as missed).
    "numeric-inconsistency": ["numeric_inconsistency", "date_inconsistency"],
    "weekday-inconsistency": ["weekday_inconsistency", "weekday_date_mismatch"],
    "stale-date": ["event_date_past", "stale_year_title"],
    "stale-review": ["review_stamp_is_publish_date", "review_overdue"],
    "price-no-as-of": ["price_no_as_of", "price_as_of_old"],
    "first-hand-claim": ["unsupported_first_hand_claim"],
    "missing-section": ["missing_required_section"],
    "affiliate-disclosure": ["affiliate_disclosure_missing"],
    "banned-character": ["banned_character"],
    "byline": ["byline_not_allowed", "byline_title_not_allowed"],
    "dead-link": ["link_broken"],
    "blocked-link": ["link_blocked", "link_unverifiable"],
    "broken-internal-link": ["link_broken_internal"],
    "entity-wrong": [],
    "seasonality": [],
    "source-mismatch": [],
}
TRAVEL_TODAY = date(2026, 10, 30)  # fixed check date for the travel sets, so the staleness rules are reproducible
TRAVEL_FIXTURES = FIXTURES / "travel"
TARGET_RECALL = 9 / 10
TARGET_MAX_CLEAN_FP = 1


def score(errors: list[dict], reports: dict[str, dict]) -> dict:
    """reports maps 'clean/<file>' or 'seeded/<file>' to a gate report."""
    detected, matched_findings = {}, set()
    for err in errors:
        report = reports[err["file"]]
        hits = [
            (i, f)
            for i, f in enumerate(report["findings"])
            if f["severity"] in COUNTED
            and ("*" in err["rules"] or f["rule"] in err["rules"])
            and (f["line"] == err["line"] or err["line"] in f.get("also", ()))
        ]
        detected[err["id"]] = [f for _, f in hits]
        matched_findings.update((err["file"], i) for i, _ in hits)

    false_pos = []
    for key, report in reports.items():
        for i, f in enumerate(report["findings"]):
            if f["severity"] in COUNTED and (key, i) not in matched_findings:
                false_pos.append({"file": key, **f})
    tp = len(matched_findings)
    hit_ids = [e["id"] for e in errors if detected[e["id"]]]
    clean_fp = [f for f in false_pos if f["file"].startswith("clean/")]
    return {
        "seeded_total": len(errors),
        "seeded_detected": len(hit_ids),
        "recall": len(hit_ids) / len(errors),
        "missed": [e["id"] for e in errors if not detected[e["id"]]],
        "true_positive_findings": tp,
        "false_positive_findings": len(false_pos),
        "precision": tp / (tp + len(false_pos)) if tp + len(false_pos) else 1.0,
        "clean_false_positives": len(clean_fp),
        "detail": {
            e["id"]: [{"rule": f["rule"], "line": f["line"], "severity": f["severity"]} for f in detected[e["id"]]]
            for e in errors
        },
        "false_positive_list": false_pos,
        "verdicts": {k: r["verdict"] for k, r in reports.items()},
    }


def _norm_text(text: str) -> str:
    return " ".join(text.lower().replace("’", "'").replace("“", '"').replace("”", '"').split())


def _matches(err: dict, quote: str) -> bool:
    """A model remark hits an error only when its quote overlaps the injected text itself.

    A quote from elsewhere in the same paragraph does not count (the review of the first version found
    three loose matches that inflated true positives)."""
    quote = _norm_text(quote)
    if len(quote) < 10:
        return False
    snippet = _norm_text(err["snippet"])
    injected = _norm_text(err.get("injected") or "")
    return snippet in quote or quote in snippet or (bool(injected) and quote in injected)


ARTIFACT_MARKERS = ("fictional practice", "software demonstration")  # demo disclaimer present only in fixtures


def score_model(
    errors: list[dict], rules: dict, model_dir: Path, set_name: str, rule_ids: set[str] | None = None
) -> dict:
    """Score the model layer alone and combined with the rules.

    A model finding (severity block/warn) hits an error when its quote lies on the error's line.
    Every other block/warn model finding counts as a false positive, so the number is strict:
    a correct but off-target remark (for example 'this claim has no link') counts against precision.
    """
    detected, tp, fps, failed, cost, artifacts = {}, 0, [], [], 0.0, 0
    clean_verdicts = {}
    root, set_name = posts_root(set_name), set_folder(set_name)
    for folder in ("clean", set_name):
        for path in sorted((root / folder).glob("*.md")):
            report_path = model_dir / f"{folder}-{path.stem}.json"
            if not report_path.exists():
                return {"status": "missing", "detail": f"{report_path.name} not found"}
            llm = json.loads(report_path.read_text(encoding="utf-8")).get("llm", {})
            if llm.get("status") != "ok":
                failed.append(f"{folder}/{path.name}: {llm.get('status')}")
                continue
            cost += llm.get("cost_usd") or 0.0
            if folder == "clean":
                clean_verdicts[path.name] = json.loads(report_path.read_text(encoding="utf-8"))["verdict"]
            for f in llm.get("findings", []):
                if f.get("severity") not in COUNTED:
                    continue
                quote = str(f.get("quote", ""))
                if any(m in quote.lower() for m in ARTIFACT_MARKERS):
                    artifacts += 1  # the 'fictional practice' line exists only in fixtures; not scored
                    continue
                hit = next((e for e in errors if e["file"] == f"{folder}/{path.name}" and _matches(e, quote)), None)
                if hit:
                    detected.setdefault(hit["id"], f)
                    tp += 1
                else:
                    fps.append(
                        {
                            "file": f"{folder}/{path.name}",
                            "severity": f["severity"],
                            "type": f.get("type"),
                            "quote": quote[:90],
                            "why": str(f.get("why", ""))[:140],
                        }
                    )
    custom_rule_ids = rule_ids is not None
    if rule_ids is None:
        rule_ids = {e["id"] for e in errors if rules["detail"][e["id"]]}
    union = rule_ids | set(detected)
    total = len(errors)
    r_tp, r_fp = rules["true_positive_findings"], rules["false_positive_findings"]
    # with a rules snapshot, recall uses the old rule state but the finding counts are the current ones:
    # do not mix the two into one precision figure
    denom = r_tp + tp + r_fp + len(fps)
    mixed = custom_rule_ids
    return {
        "status": "ok" if not failed else "partial",
        "failed": failed,
        "cost_usd": round(cost, 4),
        "model_detected": sorted(detected),
        "model_recall": len(detected) / total,
        "model_missed": sorted({e["id"] for e in errors} - set(detected)),
        "fixture_disclaimer_findings_ignored": artifacts,
        "clean_posts_not_publish_with_model": sum(1 for v in clean_verdicts.values() if v != "PUBLICAR"),
        "rules_detected_ids": sorted(rule_ids),
        "model_tp": tp,
        "model_fp": len(fps),
        "model_precision": tp / (tp + len(fps)) if tp + len(fps) else 1.0,
        "model_clean_fp": sum(1 for f in fps if f["file"].startswith("clean/")),
        "model_only_extra": sorted(set(detected) - rule_ids),
        "combined_recall": len(union) / total,
        "combined_detected": len(union),
        "combined_precision": None if mixed else ((r_tp + tp) / denom if denom else 1.0),
        "false_positive_list": fps,
    }


def render_markdown(errors: list[dict], result: dict, mode: str, llm: dict | None, set_name: str = "seeded") -> str:
    lines = [
        f"# QA gate evaluation ({set_name} set)",
        "",
        f"Link mode: **{mode}**. Errors: {result['seeded_total']} in 4 posts. Clean posts: 4.",
        "",
        f"- **Recall:** {result['seeded_detected']}/{result['seeded_total']} = {result['recall']:.0%}",
        f"- **Precision (block+warn findings):** {result['precision']:.0%} "
        f"({result['true_positive_findings']} true / {result['false_positive_findings']} false)",
        f"- **False positives on clean posts:** {result['clean_false_positives']}",
        f"- **Missed:** {', '.join(result['missed']) or 'none'}",
        "",
        "| ID | Category | Detected | Findings on the injected line |",
        "|---|---|---|---|",
    ]
    for e in errors:
        hits = result["detail"][e["id"]]
        shown = ", ".join(f"`{h['rule']}`" for h in hits) or "-"
        lines.append(f"| {e['id']} | {e['category']} | {'yes' if hits else '**NO**'} | {shown} |")
    lines += ["", "## Verdicts", "", "| Post | Verdict |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in sorted(result["verdicts"].items())]
    if result["false_positive_list"]:
        lines += ["", "## Unmatched block/warn findings", ""]
        lines += [f"- {f['file']}:{f['line']} `{f['rule']}` {f['evidence']!r}" for f in result["false_positive_list"]]
    if llm:
        lines += ["", "## Model layer", ""]
        if llm["status"] in ("ok", "partial"):
            n = result["seeded_total"]
            mixed_rule_states = llm["combined_precision"] is None
            rules_precision = (
                "n/a (recall from the snapshot rule state)" if mixed_rule_states else format(result["precision"], ".0%")
            )
            combined_precision = (
                "n/a (mixed rule states)" if mixed_rule_states else format(llm["combined_precision"], ".0%")
            )
            lines += [
                "| Layer | Recall | Precision (block+warn) | Notes |",
                "|---|---|---|---|",
                f"| Rules only | {len(llm['rules_detected_ids'])}/{n} | {rules_precision} | "
                f"{result['clean_false_positives']} false alarms on clean posts |",
                f"| Model only | {len(llm['model_detected'])}/{n} | {llm['model_precision']:.0%} "
                f"({llm['model_tp']} true / {llm['model_fp']} false) | {llm['model_clean_fp']} off-target "
                f"block/warn on clean posts; missed {', '.join(llm['model_missed']) or 'none'}; "
                f"cost ${llm['cost_usd']} |",
                f"| Rules + model | {llm['combined_detected']}/{n} | {combined_precision} | "
                f"model adds: {', '.join(llm['model_only_extra']) or 'nothing'} |",
            ]
            lines += [f"- model run failed: {x}" for x in llm["failed"]]
            lines.append(
                f"- with the model layer on, {llm['clean_posts_not_publish_with_model']}/4 clean posts are no longer "
                f"PUBLICAR; {llm['fixture_disclaimer_findings_ignored']} findings about the fixture-only "
                "'fictional practice' line were ignored"
            )
            if llm["false_positive_list"]:
                lines += ["", "Off-target model findings (block/warn):", ""]
                lines += [
                    f"- {f['file']} [{f['severity']}/{f['type']}] {f['quote']!r}: {f['why']}"
                    for f in llm["false_positive_list"]
                ]
        else:
            lines.append(f"- not scored: {llm['detail']}")

    return "\n".join(lines) + "\n"


def snapshot_ids(errors: list[dict], path: str) -> set[str] | None:
    if not path:
        return None
    m = re.search(r"[*][*]Missed:[*][*] (.*)", Path(path).read_text(encoding="utf-8"))
    if m is None:
        raise ValueError(f"{path}: no '**Missed:**' line; refusing to credit the rules with every error")
    missed = set() if m.group(1).strip() == "none" else {x.strip() for x in m.group(1).split(",")}
    unknown = missed - {e["id"] for e in errors}
    if unknown:
        raise ValueError(f"{path}: Missed lists unknown ids {sorted(unknown)}")
    return {e["id"] for e in errors} - missed


def is_travel(which: str) -> bool:
    return which.startswith("travel-")


def set_folder(which: str) -> str:
    """'travel-heldout' -> 'heldout' (folder under fixtures/travel/posts); dental sets are their own folder."""
    return which.removeprefix("travel-")


def posts_root(which: str) -> Path:
    return (TRAVEL_FIXTURES if is_travel(which) else FIXTURES) / "posts"


def load_errors(which: str) -> list[dict]:
    """Return errors with 'file' as '<folder>/<name>', 'rules', 'line' and 'snippet' filled in."""
    base, folder = (TRAVEL_FIXTURES if is_travel(which) else FIXTURES), set_folder(which)
    if folder == "seeded":
        return json.loads((base / "seeded-errors.json").read_text(encoding="utf-8"))["errors"]
    raw = json.loads((base / f"{folder}-errors.json").read_text(encoding="utf-8"))["errors"]
    out = []
    for e in raw:
        e = {**e, "file": Path(e["file"]).name}
        lines = (base / "posts" / folder / e["file"]).read_text(encoding="utf-8").splitlines()
        hits = [i + 1 for i, line in enumerate(lines) if e["snippet"] in line]
        if not hits:
            raise ValueError(f"{e['id']}: snippet not found in {folder}/{e['file']}: {e['snippet']!r}")
        out.append(
            {
                **e,
                "file": f"{folder}/{e['file']}",
                "line": 0 if e.get("whole_file") else hits[0],
                "rules": CATEGORY_RULES[e["category"]],
            }
        )
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--online", action="store_true")
    ap.add_argument(
        "--cache",
        default=str(DEFAULT_CACHE),
        help="link cache replayed in offline mode (fixtures/link-cache.json was recorded by online runs on "
        "2026-10-30, partly AFTER the errors existed; use --online or an empty cache to avoid replay)",
    )
    ap.add_argument(
        "--set",
        choices=("seeded", "heldout", "heldout2", "heldout3", "travel-seeded", "travel-heldout"),
        default="seeded",
        help="heldout = errors written blind by a separate agent (fixtures/heldout-errors.json); "
        "travel-* use fixtures/travel (site.yaml, own link cache, check date fixed at 2026-10-30)",
    )
    ap.add_argument("--with-llm", action="store_true", help="also score the model layer (needs --model-dir)")
    ap.add_argument(
        "--rules-snapshot",
        default="",
        help="EVAL markdown of an earlier (blind) rules run; its 'Missed' list defines which errors "
        "the rules are credited with when computing rules+model",
    )
    ap.add_argument(
        "--model-dir",
        default=str(DEFAULT_REPORTS / "model-sonnet"),
        help="reports directory of a run_gate.py --llm run",
    )
    ap.add_argument("--out", default=str(DEFAULT_REPORTS))
    ap.add_argument("--strict", action="store_true", help="exit 1 if the targets are missed")
    args = ap.parse_args(argv)

    errors = load_errors(args.set)
    travel = is_travel(args.set)
    clinic = load_clinic(TRAVEL_FIXTURES / "site.yaml" if travel else DEFAULT_CLINIC)
    cache = links.load_cache(
        TRAVEL_FIXTURES / "link-cache.json" if travel and args.cache == str(DEFAULT_CACHE) else args.cache
    )
    reports, root, which = {}, posts_root(args.set), set_folder(args.set)
    for folder in ("clean", which):
        for path in sorted((root / folder).glob("*.md")):
            report, _, _ = check_file(
                path,
                clinic,
                offline=not args.online,
                link_cache=cache,
                max_age_days=None,
                today=TRAVEL_TODAY if travel else None,
            )
            reports[f"{folder}/{path.name}"] = report
    result = score(errors, reports)
    llm = (
        score_model(errors, result, Path(args.model_dir), args.set, snapshot_ids(errors, args.rules_snapshot))
        if args.with_llm
        else None
    )
    mode = "online" if args.online else "offline (cached link results)"
    md = render_markdown(errors, result, mode, llm, args.set)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = "EVAL" if args.set == "seeded" else f"EVAL-{args.set}"
    if args.with_llm:
        stem += "-" + Path(args.model_dir).name
    (out / f"{stem}.md").write_text(md, encoding="utf-8")
    (out / f"{stem.lower()}.json").write_text(
        json.dumps({"link_mode": mode, **result, "llm": llm}, indent=2) + "\n", encoding="utf-8"
    )
    print(md)
    ok = result["recall"] >= TARGET_RECALL and result["clean_false_positives"] <= TARGET_MAX_CLEAN_FP
    return 0 if ok or not args.strict else 1


if __name__ == "__main__":
    sys.exit(main())
