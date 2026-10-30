"""Command line: status | estimate | run | report | validate | gold-sample."""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path

from . import db
from .anonymize import anonymize_validation
from .config import load_config
from .cost import BudgetExceeded, estimate
from .engines import build_engines
from .import_answers import import_jsonl
from .judge import anthropic_judge, apply_judge, claude_cli_judge
from .reextract import reextract
from .report import render
from .runner import run_batch
from .validate import evaluate, evaluate_real, load_gold

ROOT = Path(__file__).resolve().parent.parent
LOCAL_CONFIG = ROOT / "config" / "austin_real.local.yaml"  # real practice names; git-ignored
DEFAULT_CONFIG = LOCAL_CONFIG if LOCAL_CONFIG.exists() else ROOT / "config" / "austin_real.yaml"


def load_env(path: Path) -> None:
    """Minimal .env reader. Values go into os.environ and are never printed."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if value.strip() and not os.environ.get(key.strip()):
            os.environ[key.strip()] = value.strip().strip('"').strip("'")


def _paths(args: argparse.Namespace, cfg_name: str) -> tuple[Path, str, Path]:
    suffix = "mock" if args.mock else "real"
    db_path = Path(args.db) if args.db else ROOT / "runs" / f"{suffix}.db"
    batch = args.batch or f"{cfg_name}-{suffix}"
    raw_dir = ROOT / "runs" / "raw" / suffix
    return db_path, batch, raw_dir


def cmd_status(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    print(f"config: {cfg.name}  ({len(cfg.brands)} brands, {len(cfg.prompts)} prompts, {cfg.repetitions} reps)")
    engines, disabled = build_engines(cfg, mock=args.mock, check_env=False)
    for e in engines:
        state = f"DISABLED ({disabled[e.key]})" if e.key in disabled else "READY"
        print(f"  {e.key:15s} {state}  reps={e.reps or cfg.repetitions}")
    for key, why in disabled.items():
        if key not in {e.key for e in engines}:
            print(f"  {key:15s} DISABLED ({why})")
    print("  (key values are never printed)")
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    db_path, batch, raw_dir = _paths(args, cfg.name)
    conn = db.connect(db_path)
    summary = import_jsonl(conn, cfg, args.file, batch, raw_dir)
    print(f"imported {summary.imported} answers into batch {batch} ({summary.duplicates} already there, skipped)")
    for s in summary.skipped:
        print(f"  skipped {s}", file=sys.stderr)
    return 0 if not summary.skipped else 1


def cmd_estimate(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    engines, disabled = build_engines(cfg, mock=args.mock, only=_only(args), check_env=False)
    reps = args.reps or cfg.repetitions
    est = estimate(cfg, engines, reps)
    for k, n in est.calls_by_engine.items():
        note = f"   [{disabled[k]}: would be skipped]" if k in disabled else ""
        print(f"  {k:15s} {n:4d} calls  <= ${est.upper_usd_by_engine[k]:.2f}{note}")
    print(f"total {est.calls} calls, upper-bound ${est.upper_usd:.2f}, budget ${args.budget or cfg.budget_usd:.2f}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    engines, disabled = build_engines(cfg, mock=args.mock, only=_only(args), seed=args.seed)
    if not engines:
        print("no engines available; set keys in .env (see .env.example) or use --mock", file=sys.stderr)
        for k, why in disabled.items():
            print(f"  {k}: {why}", file=sys.stderr)
        return 2
    reps = args.reps or cfg.repetitions
    budget = args.budget or cfg.budget_usd
    est = estimate(cfg, engines, reps)
    print(f"{est.calls} calls over {len(engines)} engines, upper-bound ${est.upper_usd:.2f}, budget ${budget:.2f}")
    if not args.mock and not args.confirm_spend:
        print("real API calls cost money: re-run with --confirm-spend to proceed", file=sys.stderr)
        return 3
    db_path, batch, raw_dir = _paths(args, cfg.name)
    conn = db.connect(db_path)
    judge = None
    if args.judge:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("--judge needs ANTHROPIC_API_KEY", file=sys.stderr)
            return 2
        judge = anthropic_judge(cfg.brands)
    try:
        summary = run_batch(
            cfg,
            engines,
            conn,
            batch=batch,
            reps=reps,
            budget_usd=budget,
            raw_dir=raw_dir,
            is_mock=args.mock,
            seed=args.seed,
            backoff=0.0 if args.mock else 2.0,
            judge=judge,
        )
    except BudgetExceeded as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 4
    print(
        f"batch {batch}: ok={summary.ok} errors={summary.errors} already_done={summary.skipped_done} "
        f"spent=${summary.spent_usd:.4f}"
    )
    for note in summary.notes:
        print(f"  STOPPED EARLY: {note}")
    print(f"db: {db_path}")
    return 0


def cmd_reextract(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    db_path, batch, _ = _paths(args, cfg.name)
    n = reextract(db.connect(db_path), cfg, batch)
    print(f"re-extracted {n} stored answers in batch {batch} (no new queries); stored judge verdicts kept")
    return 0


def cmd_judge(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    db_path, batch, _ = _paths(args, cfg.name)
    conn = db.connect(db_path)
    if args.with_ == "claude_cli":
        judge = claude_cli_judge(cfg.brands)
    else:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("--with api needs ANTHROPIC_API_KEY", file=sys.stderr)
            return 2
        judge = anthropic_judge(cfg.brands)
    counts = apply_judge(conn, cfg, batch, judge, args.with_, pause=args.pause)
    print(f"judged={counts['judged']} failed={counts['failed']}")
    return 0 if not counts["failed"] else 1


def cmd_report(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    db_path, batch, _ = _paths(args, cfg.name)
    conn = db.connect(db_path)
    _, disabled = build_engines(cfg, mock=args.mock)
    default_out = ROOT / "report" / ("index.html" if args.anonymize else "local/index.html")
    out = render(
        conn,
        cfg,
        batch,
        args.out or default_out,
        validation_path=ROOT / "report" / "validation.json",
        disabled=disabled,
        anonymize=args.anonymize,
    )
    print(f"report: {out}")
    return 0


def cmd_numbers(args: argparse.Namespace) -> int:
    """Every figure quoted in RESULTS.md, computed by the same code as the report (writes report/numbers.json)."""
    from .analysis import build
    from .anonymize import anonymize_config, remap_data
    from .stats import wilson

    cfg = load_config(args.config)
    db_path, batch, _ = _paths(args, cfg.name)
    conn = db.connect(db_path)
    d = build(conn, cfg, batch)
    if args.anonymize:
        d = remap_data(d, cfg)
        cfg = anonymize_config(cfg)
    out: dict = {"batch": batch, "name_overlap": d["name_overlap"], "engines": {}}
    for e in d["engines"]:
        ids = [
            r["id"]
            for r in conn.execute(
                "SELECT id FROM run WHERE batch = ? AND engine = ? AND status = 'ok' AND answer_present = 1", (batch, e)
            )
        ]
        named = sum(
            1
            for i in ids
            if conn.execute(
                "SELECT 1 FROM mention WHERE run_id = ? AND matched_by IN ('regex','both')", (i,)
            ).fetchone()
        )
        lo, hi = wilson(named, len(ids))
        out["engines"][e] = {
            "answers": len(ids),
            "any_tracked_named": named,
            "any_tracked_named_ci95": [lo, hi],
            "reps": d["engine_summary"][e]["reps"],
            "rates": {
                b.name: {k: d["rates"][b.id][e][k] for k in ("k", "n", "rate", "lo", "hi", "k_cited")}
                for b in cfg.brands
            },
        }
    own = conn.execute(
        "SELECT COUNT(DISTINCT c.run_id) AS n FROM citation c JOIN run r ON r.id = c.run_id "
        "WHERE r.batch = ? AND c.kind = 'cited' AND c.brand_id IS NOT NULL",
        (batch,),
    ).fetchone()["n"]
    out["own_site_cited_in_answers"] = own
    out["top_domains"] = [(t["domain"], t["runs"], t["share"]) for t in d["top_domains"][:6]]
    out["answers_total"] = sum(v["answers"] for v in out["engines"].values())
    path = ROOT / "report" / ("numbers.json" if args.anonymize else "local/numbers.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1, default=lambda x: None), encoding="utf-8")
    print(json.dumps(out, indent=1, default=lambda x: None))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    result = evaluate(load_gold(args.gold), cfg.brands)
    out = Path(args.out or ROOT / "report" / "validation.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    m, c = result["mentioned"], result["cited"]
    print(f"items={result['n_items']}  exact={result['item_exact_match']['k']}/{result['item_exact_match']['n']}")
    print(
        f"mention  P={m['precision']:.3f} R={m['recall']:.3f} F1={m['f1']:.3f}  "
        f"(tp={m['tp']} fp={m['fp']} fn={m['fn']})"
    )
    print(
        f"citation P={c['precision']:.3f} R={c['recall']:.3f} F1={c['f1']:.3f}  "
        f"(tp={c['tp']} fp={c['fp']} fn={c['fn']})"
    )
    for e in result["errors"]:
        print(f"  {e['id']} {e['field']}: fp={e['false_positive']} fn={e['false_negative']}  [{e['note']}]")
    return 0


def cmd_validate_real(args: argparse.Namespace) -> int:
    """Score regex vs LLM judge on hand-labelled REAL answers (gold/gold_real.jsonl, ids are run ids)."""
    cfg = load_config(args.config)
    db_path, _, _ = _paths(args, cfg.name)
    conn = db.connect(db_path)
    verdicts = {}
    for r in conn.execute("SELECT run_id, verdict_json FROM judge_verdict"):
        verdicts[f"run{r['run_id']}"] = set(json.loads(r["verdict_json"])["tracked"])
    result = anonymize_validation(evaluate_real(load_gold(args.gold), cfg.brands, verdicts), cfg)
    out = Path(args.out or ROOT / "report" / "validation_real.json")  # relabelled Practice A-H, no notes
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(f"items={result['n_items']} judged={result['n_judged']} true mentions={result['n_true_mentions']}")
    for k in ("regex", "judge", "either", "both"):
        m = result[k]
        print(f"  {k:7s} P={m['precision']:.3f} R={m['recall']:.3f} (tp={m['tp']} fp={m['fp']} fn={m['fn']})")
    for e in result["errors"]:
        print(f"  {e['id']} {e['who']}: fp={e['false_positive']} fn={e['false_negative']}")
    return 0


def cmd_gold_sample(args: argparse.Namespace) -> int:
    """Dump random stored answers to label by hand (fill `mentioned` and `cited`, then validate)."""
    cfg = load_config(args.config)
    db_path, batch, _ = _paths(args, cfg.name)
    conn = db.connect(db_path)
    rows = conn.execute(
        "SELECT id, engine, answer_text FROM run WHERE batch = ? AND status = 'ok' AND answer_present = 1", (batch,)
    ).fetchall()
    random.Random(args.seed).shuffle(rows)
    out = Path(args.out or ROOT / "gold" / "to_label.jsonl")
    with out.open("w", encoding="utf-8") as fh:
        for r in rows[: args.n]:
            urls = [
                c["url"]
                for c in conn.execute("SELECT url FROM citation WHERE run_id = ? AND kind = 'cited'", (r["id"],))
            ]
            fh.write(
                json.dumps(
                    {
                        "id": f"run{r['id']}",
                        "note": r["engine"],
                        "answer": r["answer_text"],
                        "cited_urls": urls,
                        "mentioned": None,
                        "cited": None,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    print(f"wrote {min(args.n, len(rows))} answers to {out}; fill 'mentioned' and 'cited' (brand ids)")
    return 0


def _only(args: argparse.Namespace) -> list[str] | None:
    return args.engines.split(",") if getattr(args, "engines", None) else None


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vistrack", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--config", default=str(DEFAULT_CONFIG))
        sp.add_argument("--mock", action="store_true", help="synthetic engines, no network, no cost")
        sp.add_argument("--db")
        sp.add_argument("--batch")

    sp = sub.add_parser("status", help="which engines have keys (values never shown)")
    common(sp)
    sp.set_defaults(fn=cmd_status)
    sp = sub.add_parser("estimate", help="upper-bound cost before spending")
    common(sp)
    sp.add_argument("--reps", type=int)
    sp.add_argument("--budget", type=float)
    sp.add_argument("--engines")
    sp.set_defaults(fn=cmd_estimate)
    sp = sub.add_parser("run", help="run a batch")
    common(sp)
    sp.add_argument("--reps", type=int)
    sp.add_argument("--budget", type=float)
    sp.add_argument("--engines")
    sp.add_argument("--seed", type=int, default=0)
    sp.add_argument("--judge", action="store_true")
    sp.add_argument("--confirm-spend", action="store_true", help="required for real (paid) API calls")
    sp.set_defaults(fn=cmd_run)
    sp = sub.add_parser("import", help="import answers pasted by hand from consumer apps (JSONL)")
    common(sp)
    sp.add_argument("--file", required=True)
    sp.set_defaults(fn=cmd_import)
    sp = sub.add_parser("reextract", help="recompute mentions/citations from stored answers")
    common(sp)
    sp.set_defaults(fn=cmd_reextract)
    sp = sub.add_parser("judge", help="LLM-judge every stored answer (adds judge flags)")
    common(sp)
    sp.add_argument("--with", dest="with_", choices=["claude_cli", "api"], default="claude_cli")
    sp.add_argument("--pause", type=float, default=3.0)
    sp.set_defaults(fn=cmd_judge)
    sp = sub.add_parser("report", help="render report/index.html")
    common(sp)
    sp.add_argument("--out")
    sp.add_argument(
        "--anonymize",
        action="store_true",
        help="label practices Practice A-H, drop other business names: the version that may be shared "
        "(default output: report/index.html; without it: report/local/index.html, git-ignored)",
    )
    sp.set_defaults(fn=cmd_report)
    sp = sub.add_parser("numbers", help="print/write every figure used in RESULTS.md")
    common(sp)
    sp.add_argument("--anonymize", action="store_true", help="Practice A-H labels; writes report/numbers.json")
    sp.set_defaults(fn=cmd_numbers)
    sp = sub.add_parser("validate", help="score the extractor on the gold set")
    common(sp)
    sp.add_argument("--gold", default=str(ROOT / "gold" / "gold_set.jsonl"))
    sp.add_argument("--out")
    sp.set_defaults(fn=cmd_validate)
    sp = sub.add_parser("validate-real", help="regex vs LLM judge on hand-labelled real answers")
    common(sp)
    sp.add_argument("--gold", default=str(ROOT / "gold" / "gold_real.local.jsonl"))
    sp.add_argument("--out")
    sp.set_defaults(fn=cmd_validate_real)
    sp = sub.add_parser("gold-sample", help="export stored answers to label")
    common(sp)
    sp.add_argument("--n", type=int, default=40)
    sp.add_argument("--seed", type=int, default=0)
    sp.add_argument("--out")
    sp.set_defaults(fn=cmd_gold_sample)
    return p


def main(argv: list[str] | None = None) -> int:
    load_env(ROOT / ".env")
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
