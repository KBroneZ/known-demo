"""Command line entry point: python run_gate.py <posts or dirs> [options]."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from . import links
from .findings import VERDICT_BLOCK, VERDICT_FIX, VERDICT_OK
from .gate import check_file, internal_error_report
from .llm import build_prompt, merge_verdict, run_backend
from .loader import load_clinic

QA_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CLINIC = QA_ROOT / "fixtures" / "clinic.yaml"
DEFAULT_CACHE = QA_ROOT / "fixtures" / "link-cache.json"
DEFAULT_REPORTS = QA_ROOT / "reports"
EXIT_CODES = {VERDICT_OK: 0, VERDICT_FIX: 1, VERDICT_BLOCK: 2}


EXIT_ERROR = 3  # no posts, unreadable input, or a crash outside a post. CI should fail on any code >= 2.


class GateInputError(Exception):
    pass


def collect_posts(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            files.extend(sorted(p.glob("*.md")))
        elif p.is_file():
            files.append(p)
        else:
            raise GateInputError(f"no such file or directory: {raw}")
    if not files:
        raise GateInputError("no .md posts found in the given paths; refusing to report PUBLICAR on nothing")
    return files


def report_name(path: Path) -> str:
    """<folder>-<stem>, so posts with the same name in different folders do not overwrite each other."""
    return f"{path.parent.name or 'post'}-{path.stem}"


def summary_markdown(reports: list[dict]) -> str:
    lines = [
        "# QA gate summary",
        "",
        "| Post | Verdict | Block | Warn | Info | Top findings |",
        "|---|---|---|---|---|---|",
    ]
    for r in reports:
        top = [f"`{f['rule']}`@{f['line']}" for f in r["findings"] if f["severity"] != "info"][:4]
        c = r["counts"]
        lines.append(
            f"| {r['name']} | **{r['verdict']}** | {c['block']} | {c['warn']} | {c['info']} | {', '.join(top) or '-'} |"
        )
    counts = {v: sum(1 for r in reports if r["verdict"] == v) for v in (VERDICT_BLOCK, VERDICT_FIX, VERDICT_OK)}
    lines += [
        "",
        f"BLOQUEAR: {counts[VERDICT_BLOCK]} | CORREGIR: {counts[VERDICT_FIX]} | PUBLICAR: {counts[VERDICT_OK]}",
    ]
    modes = sorted({r["link_mode"] for r in reports})
    lines.append(f"Link mode: {', '.join(modes)}")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="run_gate",
        description="Two-layer QA gate for AI-written dental posts.",
        epilog="Exit codes: 0 PUBLICAR, 1 CORREGIR, 2 BLOQUEAR (also: a post crashed the gate), "
        "3 gate error (no posts, bad path, crash). Fail CI on any code >= 2.",
    )
    ap.add_argument("paths", nargs="+", help="post .md files or directories")
    ap.add_argument("--clinic", default=str(DEFAULT_CLINIC))
    ap.add_argument("--out", default=str(DEFAULT_REPORTS), help="reports directory")
    ap.add_argument("--offline", action="store_true", help="do not touch the network; use the link cache")
    ap.add_argument("--link-cache", default=str(DEFAULT_CACHE))
    ap.add_argument(
        "--max-cache-age-days",
        type=int,
        default=links.CACHE_MAX_AGE_DAYS,
        help="offline: cached link results older than this count as missing (negative = no limit)",
    )
    ap.add_argument(
        "--update-cache",
        action="store_true",
        help="online run: record definitive link results (2xx/3xx, 404/410, NXDOMAIN) to the cache",
    )
    ap.add_argument("--timeout", type=float, default=links.DEFAULT_TIMEOUT)
    ap.add_argument(
        "--llm", choices=("none", "claude", "codex"), default="none", help="model review: none = write prompt only"
    )
    ap.add_argument("--llm-model", default="", help="model alias passed to `claude --model`")
    ap.add_argument(
        "--llm-independent",
        action="store_true",
        help="do not show the model the deterministic findings (to measure the model layer alone)",
    )
    ap.add_argument("--llm-effort", default="", help="reasoning effort passed to the codex backend")
    ap.add_argument(
        "--today", default="", help="check date YYYY-MM-DD for the staleness rules (travel profile); default: today"
    )
    return ap


def run(args: argparse.Namespace) -> int:
    posts = collect_posts(args.paths)
    clinic = load_clinic(args.clinic)
    try:
        today = date.fromisoformat(args.today) if args.today else None
    except ValueError:
        raise GateInputError(f"--today must be YYYY-MM-DD, got {args.today!r}") from None
    cache = links.load_cache(args.link_cache)
    max_age = args.max_cache_age_days if args.max_cache_age_days >= 0 else None
    out_dir = Path(args.out)
    (out_dir / "prompts").mkdir(parents=True, exist_ok=True)
    (out_dir / "llm").mkdir(parents=True, exist_ok=True)

    reports, new_cache, model_failed = [], dict(cache), []
    for path in posts:
        name = report_name(path)
        prompt_path = out_dir / "prompts" / f"{name}.prompt.md"
        try:
            report, fresh, post = check_file(path, clinic, args.offline, cache, args.timeout, max_age, today)
            prompt = build_prompt(post, clinic, report["findings"], args.llm_independent, today)
            prompt_path.write_text(prompt, encoding="utf-8")
            report["llm"] = run_backend(
                args.llm, prompt, prompt_path, out_dir / "llm" / f"{name}.llm.txt", args.llm_model, args.llm_effort
            )
        except Exception as exc:  # fail closed: a crash on one post is a BLOQUEAR, not a pass
            report, fresh = internal_error_report(path, exc, args.offline), {}
            print(f"gate crashed on {path}: {type(exc).__name__}: {exc}", file=sys.stderr)
        report["name"] = name
        checked_on = date.today().isoformat()
        new_cache.update({u: {**r, "checked": checked_on} for u, r in fresh.items() if links.is_persistable(r)})
        report = merge_verdict(report)
        if args.llm != "none" and report["llm"].get("status") != "ok":
            model_failed.append(name)
            print(
                f"warning: model layer did not run for {name}: {report['llm'].get('status')} "
                f"{report['llm'].get('detail', '')}".strip(),
                file=sys.stderr,
            )
        (out_dir / f"{name}.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        reports.append(report)
        print(f"{report['verdict']:9} {name}  (block {report['counts']['block']}, warn {report['counts']['warn']})")

    if args.update_cache and not args.offline:
        links.save_cache(args.link_cache, new_cache)
    (out_dir / "SUMMARY.md").write_text(summary_markdown(reports), encoding="utf-8")
    code = max(EXIT_CODES[r["verdict"]] for r in reports)
    return max(code, 1) if model_failed else code  # asked for a model review that did not happen: not a clean pass


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except GateInputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except Exception as exc:  # anything else outside a post: never look like CORREGIR or PUBLICAR
        print(f"gate error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
