"""Command line: `python run_pipeline.py topics|run ...`."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from . import clinicdata, sitefiles, topics
from .clinicdata import PIPELINE_ROOT
from .runner import STATUS_DONE, ApprovalError, Config, approve, run_all

OUT_ROOT = PIPELINE_ROOT / "out"


def pick_for(site, per_clinic: int, services: list[str] | None, refresh: bool):
    candidates = topics.candidates_for(site, refresh) + topics.seed_candidates(site)
    if services:
        by_key: dict = {}
        for c in candidates:  # real questions come first; a seed question only fills a service that has none
            by_key.setdefault(c.service, c)
            by_key.setdefault(c.question, c)  # a topic can also be picked by its exact question
        missing = [s for s in services if s not in by_key]
        if missing:
            raise SystemExit(f"{site.id}: no candidate topic for {missing}; see `topics`")
        return [by_key[s] for s in services]
    return topics.choose(site, per_clinic, refresh)


def parse_picks(values: list[str]) -> dict[str, list[str]]:
    out = {}
    for value in values or []:
        site_id, _, names = value.partition("=")
        out[site_id] = [n.strip() for n in names.split(";") if n.strip()]
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="run_pipeline", description="Blog post pipeline: topic -> brief -> draft -> QA -> fix -> local PR."
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    ap_sync = sub.add_parser(
        "sync-pages", help="add a /blog/<slug> route to clinic.yaml `pages` for every post that lacks one"
    )
    ap_sync.add_argument("--site", action="append")
    ap_app = sub.add_parser("approve", help="a person accepts a needs-human post (CORREGIR left) and publishes it")
    ap_app.add_argument("post_dir")
    ap_app.add_argument("--by", required=True, help="who is accepting the remaining findings")
    ap_app.add_argument("--note", default="")
    for name in ("topics", "run"):
        p = sub.add_parser(name)
        p.add_argument("--site", action="append", help="clinic id (default: every site)")
        p.add_argument("--per-clinic", type=int, default=2)
        p.add_argument(
            "--pick",
            action="append",
            help="'clinic-a=Teeth whitening;Root canal therapy' to choose services (the editor's topic approval)",
        )
        p.add_argument(
            "--explain",
            action="store_true",
            help="topics: show every question title and why it was accepted or rejected",
        )
        p.add_argument(
            "--refresh-topics", action="store_true", help="ignore the question cache and ask the archive again"
        )
    run = sub.choices["run"]
    run.add_argument("--draft-model", default="sonnet")
    run.add_argument("--qa-model", default="sonnet")
    run.add_argument("--max-rounds", type=int, default=2)
    run.add_argument("--no-publish", action="store_true", help="never copy to the website")
    run.add_argument("--no-model-qa", action="store_true", help="rules only (no model review)")
    run.add_argument(
        "--offline", action="store_true", help="QA link check reads no network (unverified links become CORREGIR)"
    )
    run.add_argument("--dry-run", action="store_true", help="stop after the brief; no model calls")
    run.add_argument("--run-id", default=datetime.now().strftime("%Y-%m-%dT%H%M"))
    run.add_argument("--out", default=str(OUT_ROOT))
    args = ap.parse_args(argv)
    if args.cmd == "sync-pages":
        for sid in args.site or clinicdata.list_sites():
            added = sitefiles.sync_posts(clinicdata.load_site(sid).root)
            print(f"{sid}: {', '.join(added) if added else 'nothing to add'}")
        return 0
    if args.cmd == "approve":
        post_dir = Path(args.post_dir)
        site = clinicdata.load_site(json.loads((post_dir / "metrics.json").read_text(encoding="utf-8"))["clinic"])
        try:
            result = approve(post_dir, site, args.by, args.note)
        except ApprovalError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 3
        print(f"published {result['published_to']} (approved by {args.by}; overrode {result['approval']['overrode']})")
        return 0

    site_ids = args.site or clinicdata.list_sites()
    picks_by_site = parse_picks(args.pick)
    picks = []
    for sid in site_ids:
        site = clinicdata.load_site(sid)
        for cand in pick_for(site, args.per_clinic, picks_by_site.get(sid), args.refresh_topics):
            picks.append((site, cand))
    if args.cmd == "topics" and args.explain:
        for sid in site_ids:
            for row in topics.explain(clinicdata.load_site(sid)):
                print(f"{sid} | {row['service']} | {row['comments']:>3} | {row['title'][:70]} | {row['decision']}")
        return 0
    if args.cmd == "topics":
        for site, c in picks:
            print(f"{site.id} | {c.service} | {c.comments} comments | {c.source} {c.source_id} | {c.question}")
        return 0
    cfg = Config(
        args.draft_model,
        args.qa_model,
        args.max_rounds,
        not args.no_publish,
        not args.no_model_qa,
        args.offline,
        args.dry_run,
    )
    summary = run_all(picks, cfg, Path(args.out), args.run_id)
    for r in summary["posts"]:
        print(
            f"{r['status']:12} {r['clinic']}/{r.get('slug', r['service'])}  path={'>'.join(r['verdict_path']) or '-'} "
            f"rounds={r['rounds']} ${r['cost_usd']} {r['wall_seconds']}s"
        )
    print(f"total ${summary['total_cost_usd']} in {summary['total_wall_seconds']}s -> {Path(args.out) / args.run_id}")
    blocked = [r for r in summary["posts"] if r["status"] not in STATUS_DONE]
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
