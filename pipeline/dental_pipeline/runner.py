"""Orchestrate one post: brief -> draft -> QA -> up to N auto-fix rounds -> local PR folder -> optional publish.

Verdict policy (same words as the QA gate):
  PUBLICAR  copy the post to the website and stop.
  CORREGIR  ask the model to fix exactly the reported problems, then QA again; at most `max_rounds` times.
  BLOQUEAR  stop at once. A person reviews; nothing is copied.
A review that cannot be read, or that crashes, is never a pass: the post stops for a person.
"""

from __future__ import annotations

import difflib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from qa_gate.findings import VERDICT_BLOCK, VERDICT_FIX, VERDICT_OK
from qa_gate.paths import display_path

from . import brief as brief_mod
from . import claude, draft, review, sitefiles
from .clinicdata import Site
from .topics import Candidate

FOOTER = "{name} is a fictional practice created for a software demonstration. This post is sample content.\n"
KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
STATUS_DONE = ("published", "passed-not-published", "dry-run")  # statuses that do not need a person


@dataclass
class Config:
    draft_model: str = "sonnet"
    qa_model: str = "sonnet"
    max_rounds: int = 2
    publish: bool = True
    use_model_qa: bool = True
    offline: bool = False
    dry_run: bool = False  # stop after the brief: no model calls
    today: date | None = None


@dataclass
class PostRun:
    site: Site
    cand: Candidate
    calls: list = field(default_factory=list)
    stages: dict = field(default_factory=dict)
    qa: list = field(default_factory=list)


def timed(run: PostRun, stage: str, fn):
    t0 = time.perf_counter()
    try:
        return fn()
    finally:
        run.stages[stage] = round(run.stages.get(stage, 0.0) + time.perf_counter() - t0, 2)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def model_call(run: PostRun, stage: str, prompt: str, model: str) -> claude.Call:
    try:
        result = timed(run, stage, lambda: claude.call(stage, prompt, model, draft.SYSTEM_PROMPT))
    except claude.ClaudeError as exc:  # a failed call can still have cost money: keep it in the totals
        run.calls.append(
            {
                "stage": f"{stage} (failed)",
                "model": model,
                "cost_usd": round(getattr(exc, "cost_usd", 0.0), 5),
                "seconds": 0,
                "error": str(exc)[:200],
            }
        )
        raise
    run.calls.append(result.record())
    return result


def draft_file(brief: dict, answer: str, taken: set[str], today: date | None) -> tuple[str, draft.Parsed, str]:
    parsed = draft.parse_answer(answer)
    slug = draft.unique_slug(parsed.title, taken)  # raises DraftError when the title yields no slug
    return draft.assemble(parsed, brief, slug, today), parsed, slug


def crashed_review(name: str, exc: Exception) -> dict:
    """A crash inside the QA step fails closed: BLOQUEAR, and the run goes on with the next post."""
    finding = {
        "rule": "qa_crashed",
        "severity": "block",
        "line": 0,
        "evidence": f"{type(exc).__name__}: {exc}"[:200],
        "message": "The QA step crashed on this post; treat it as not reviewed.",
    }
    return {
        "name": name,
        "rules_verdict": VERDICT_BLOCK,
        "rules_findings": [finding],
        "model": {"status": "skipped"},
        "verdict": VERDICT_BLOCK,
        "crashed": True,
        "needs_person": True,
        "needs_person_reason": f"QA crashed ({type(exc).__name__}: {str(exc)[:120]})",
    }


def safe_review(run: PostRun, text: str, post_dir: Path, name: str, cfg: Config, use_model: bool) -> dict:
    try:
        return timed(
            run, "qa", lambda: review.review(text, run.site, post_dir, name, cfg.qa_model, use_model, cfg.offline)
        )
    except Exception as exc:
        return crashed_review(name, exc)


def run_post(cand: Candidate, site: Site, cfg: Config, run_dir: Path) -> dict:
    run = PostRun(site, cand)
    started = time.perf_counter()
    brief = timed(run, "brief", lambda: brief_mod.build_brief(site, cand))
    post_dir = run_dir / f"{site.id}--{draft.slugify(cand.service)}"
    write(post_dir / "brief.md", brief_mod.render_markdown(brief))
    write(post_dir / "brief.json", json.dumps(brief, indent=2, ensure_ascii=False))
    summary = {
        "clinic": site.id,
        "service": cand.service,
        "topic": cand.question,
        "dir": post_dir.name,
        "status": "dry-run",
        "rounds": 0,
        "verdict_path": [],
        "human_review": [],
    }
    if cfg.dry_run:
        return finish(run, summary, post_dir, started, None)

    taken = set(site.posts) | {p.stem for p in site.posts_dir.glob("*.md")}
    try:
        first = model_call(run, "draft", draft.draft_prompt(brief), cfg.draft_model)
        text, parsed, slug = draft_file(brief, first.text, taken, cfg.today)
        problems = draft.validate(parsed)
        if problems:  # one format retry, counted as a normal model call
            findings = [
                {"rule": "format", "severity": "block", "line": 0, "evidence": p, "message": p} for p in problems
            ]
            again = model_call(
                run, "draft-format-retry", draft.fix_prompt(brief, first.text, findings), cfg.draft_model
            )
            text, parsed, slug = draft_file(brief, again.text, taken, cfg.today)
            problems = draft.validate(parsed)
            if problems:
                raise draft.DraftError("; ".join(problems))
    except (claude.ClaudeError, draft.DraftError) as exc:
        summary.update(status="draft-failed", error=str(exc), human_review=[f"Draft stage failed: {exc}"])
        return finish(run, summary, post_dir, started, None)

    summary["slug"] = slug
    write(post_dir / "draft.md", text)
    current = text
    for rnd in range(cfg.max_rounds + 1):
        result = safe_review(run, current, post_dir, f"r{rnd}", cfg, cfg.use_model_qa)
        if result["model"].get("status") == "ok":
            run.calls.append(
                {
                    "stage": f"qa-r{rnd}",
                    "model": cfg.qa_model,
                    "cost_usd": round(result["model"]["cost_usd"], 5),
                    "seconds": result["model"]["seconds"],
                }
            )
        run.qa.append(result)
        write(post_dir / f"qa-r{rnd}.json", json.dumps(result, indent=2, ensure_ascii=False))
        summary["verdict_path"].append(result["verdict"])
        if result["verdict"] != VERDICT_FIX or rnd == cfg.max_rounds or result.get("needs_person"):
            break  # nothing left to auto-fix: PUBLICAR, BLOQUEAR, out of rounds, or the review cannot be read
        findings = review.findings_for_fix(result)
        try:
            fixed = model_call(run, f"fix-r{rnd + 1}", draft.fix_prompt(brief, current, findings), cfg.draft_model)
            current = draft.assemble(draft.parse_answer(fixed.text), brief, slug, cfg.today)
        except (claude.ClaudeError, draft.DraftError) as exc:
            summary.update(status="fix-failed", error=str(exc))
            break
        write(post_dir / f"candidate-r{rnd + 1}.md", current)
        summary["rounds"] = rnd + 1

    verdict = run.qa[-1]["verdict"]
    write(
        post_dir / "changes.diff",
        "".join(
            difflib.unified_diff(text.splitlines(True), current.splitlines(True), "draft.md", "final-candidate.md")
        ),
    )
    return finish(run, summary, post_dir, started, (verdict, current, slug), cfg)


def human_items(summary: dict, run: PostRun, verdict: str, rounds: int) -> list[str]:
    items = []
    if summary.get("status") in ("fix-failed", "draft-failed", "qa-crashed") or summary.get("error"):
        items.append(f"Pipeline error: {summary.get('error') or run.qa[-1].get('needs_person_reason')}")
    last = run.qa[-1] if run.qa else {}
    if last.get("needs_person") and summary.get("status") != "qa-crashed":
        items.append(f"The automatic review could not give a usable answer: {last['needs_person_reason']}")
    if verdict == VERDICT_BLOCK:
        for f in last.get("rules_findings", []):
            if f["severity"] == "block":
                items.append(f"BLOQUEAR (rules) {f['rule']} line {f['line']}: {f['evidence']!r}")
        for f in last.get("model", {}).get("findings", []):
            if f["severity"] == "block":
                quote = str(f.get("quote"))[:100]
                items.append(f"BLOQUEAR (model only, confirm or dismiss) {f.get('type')}: {quote!r}: {f.get('why')}")
    elif verdict == VERDICT_FIX and not last.get("needs_person"):
        items.append(
            f"Still CORREGIR after {rounds} auto-fix round(s): "
            + "; ".join(f"{f['rule']}" for f in review.findings_for_fix(last))[:300]
        )
    elif verdict == VERDICT_OK:
        items.append("Dentist sign-off on clinical statements (reviewer of record: see reviewed_by)")
        items.append("Open each external link in a browser (the check only fetches status codes)")
        if rounds:
            items.append("Skim changes.diff: the model rewrote text to satisfy the reviewer")
        warned = sum(1 for q in run.qa for f in q["model"].get("findings", []))
        if warned:
            items.append(f"{warned} model remark(s) were raised in earlier rounds; see qa-r*.json")
        tips = sum(len(q["model"].get("suggestions", [])) for q in run.qa)
        if tips:
            items.append(f"{tips} model style suggestion(s) were logged and did not block; see qa-r*.json")
        if summary["status"] == "passed-not-published":
            items.append("Passed the gate but was NOT copied to the website (--no-publish)")
    return items


def publish(site: Site, slug: str, final_text: str) -> bool:
    """Write the post and register its route in clinic.yaml; if the second step fails, the first is undone.
    Returns whether a route line was added (False for a site that has no `pages` list)."""
    if not KEBAB.match(slug or ""):
        raise sitefiles.PagesEditError(f"refusing to publish with slug {slug!r}")
    target = site.posts_dir / f"{slug}.md"
    write(target, final_text)
    try:
        return sitefiles.add_page_route(site.root / "clinic.yaml", f"/blog/{slug}")
    except Exception as exc:
        target.unlink(missing_ok=True)
        raise sitefiles.PagesEditError(str(exc)) from exc


def final_bytes_ok(run: PostRun, final_text: str, post_dir: Path, cfg: Config) -> str:
    """The rules run once more on the exact text that would be published (footer included). '' when it passes."""
    result = safe_review(run, final_text, post_dir, "final", cfg, use_model=False)
    if result["verdict"] == VERDICT_OK:
        return ""
    bad = [f"{f['rule']}: {f['evidence'][:60]}" for f in result["rules_findings"] if f["severity"] in ("block", "warn")]
    return "the text to be published does not pass the rules: " + "; ".join(bad)[:300]


def finish(run: PostRun, summary: dict, post_dir: Path, started: float, outcome, cfg: Config | None = None) -> dict:
    if outcome is not None:
        verdict, current, slug = outcome
        summary["verdict"] = verdict
        crashed = bool(run.qa and run.qa[-1].get("crashed"))
        if summary["status"] == "fix-failed":
            pass
        elif crashed:
            summary["status"] = "qa-crashed"
            summary["error"] = run.qa[-1]["needs_person_reason"]
        elif verdict == VERDICT_OK:
            summary["status"] = "published" if (cfg and cfg.publish) else "passed-not-published"
        else:
            summary["status"] = "needs-human"
        footer = FOOTER.format(name=run.site.data["name"])
        final_text = current.rstrip("\n") + "\n\n" + footer
        if verdict == VERDICT_OK and summary["status"] in ("published", "passed-not-published"):
            write(post_dir / "final.md", final_text)
            target = run.site.posts_dir / f"{slug}.md"
            problem = final_bytes_ok(run, final_text, post_dir, cfg or Config())
            if problem:
                summary.update(status="needs-human", error=problem)
            elif summary["status"] == "published" and target.exists():
                summary.update(status="needs-human", error=f"{target.name} already exists; refusing to overwrite")
            elif summary["status"] == "published":
                try:
                    summary["pages_route_added"] = publish(run.site, slug, final_text)
                    summary["published_to"] = display_path(target)
                except sitefiles.PagesEditError as exc:
                    summary.update(
                        status="needs-human",
                        error=f"could not register the route in clinic.yaml, nothing was published: {exc}",
                    )
        if summary["status"] not in STATUS_DONE:
            write(post_dir / "needs-human.md", current)
        summary["human_review"] = human_items(summary, run, verdict, summary["rounds"])
    summary["calls"] = run.calls
    summary["stage_seconds"] = run.stages
    summary["cost_usd"] = round(sum(c["cost_usd"] for c in run.calls), 4)
    summary["input_tokens"] = sum(c.get("input_tokens", 0) for c in run.calls)
    summary["output_tokens"] = sum(c.get("output_tokens", 0) for c in run.calls)
    summary["wall_seconds"] = round(time.perf_counter() - started, 1)
    write(post_dir / "metrics.json", json.dumps(summary, indent=2, ensure_ascii=False))
    write(post_dir / "pr.md", render_pr(summary))
    return summary


def render_pr(s: dict) -> str:
    lines = [
        f"# Local PR: {s.get('slug', s['service'])} ({s['clinic']})",
        "",
        f"- Status: **{s['status']}**; verdict path: {' -> '.join(s['verdict_path']) or 'n/a'}; "
        f"auto-fix rounds: {s['rounds']}",
        f"- Topic: {s['topic']}",
        f"- Cost: ${s['cost_usd']} ({s['input_tokens']} input / {s['output_tokens']} output tokens, "
        "excluding QA calls' tokens)",
        f"- Time: {s['wall_seconds']} s wall ({', '.join(f'{k} {v}s' for k, v in s['stage_seconds'].items())})",
        "",
        "## A person must",
        "",
    ]
    lines += [f"- [ ] {item}" for item in s["human_review"]] or ["- nothing (dry run)"]
    files = {
        "published": "final.md (copied to the website)",
        "passed-not-published": "final.md (passed the gate; NOT copied to the website)",
    }.get(s["status"], "needs-human.md (not published)")
    lines += ["", "## Files", "", "brief.md, draft.md, qa-r*.json, changes.diff, " + files]
    return "\n".join(lines) + "\n"


def crashed_post(cand: Candidate, site: Site, exc: Exception) -> dict:
    return {
        "clinic": site.id,
        "service": cand.service,
        "topic": cand.question,
        "dir": "",
        "status": "crashed",
        "rounds": 0,
        "verdict_path": [],
        "error": f"{type(exc).__name__}: {exc}"[:300],
        "calls": [],
        "stage_seconds": {},
        "cost_usd": 0.0,
        "input_tokens": 0,
        "output_tokens": 0,
        "wall_seconds": 0.0,
        "human_review": [f"The pipeline crashed on this topic: {type(exc).__name__}: {str(exc)[:200]}"],
    }


def run_all(picks: list[tuple[Site, Candidate]], cfg: Config, out_root: Path, run_id: str) -> dict:
    run_dir = out_root / run_id
    results = []
    t0 = time.perf_counter()

    def snapshot() -> dict:
        summary = {
            "run_id": run_id,
            "draft_model": cfg.draft_model,
            "qa_model": cfg.qa_model,
            "max_rounds": cfg.max_rounds,
            "posts": results,
            "total_cost_usd": round(sum(r["cost_usd"] for r in results), 4),
            "total_wall_seconds": round(time.perf_counter() - t0, 1),
        }
        write(run_dir / "run.json", json.dumps(summary, indent=2, ensure_ascii=False))
        write(run_dir / "RUN.md", render_run(summary))
        return summary

    for site, cand in picks:
        try:
            results.append(run_post(cand, site, cfg, run_dir))
        except Exception as exc:
            results.append(crashed_post(cand, site, exc))
        snapshot()  # written after every post, so a later crash cannot lose earlier results
    return snapshot()


def render_run(s: dict) -> str:
    lines = [
        f"# Pipeline run {s['run_id']}",
        "",
        f"Draft model `{s['draft_model']}`, QA model `{s['qa_model']}`, max {s['max_rounds']} auto-fix rounds.",
        "",
        "| Post | Status | Verdict path | Rounds | Cost | Time | Model calls |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in s["posts"]:
        lines.append(
            f"| {r['clinic']} / {r.get('slug', r['service'])} | {r['status']} | "
            f"{' -> '.join(r['verdict_path']) or '-'} | "
            f"{r['rounds']} | ${r['cost_usd']} | {r['wall_seconds']} s | {len(r['calls'])} |"
        )
    lines += ["", f"Total: ${s['total_cost_usd']} and {s['total_wall_seconds']} s."]
    return "\n".join(lines) + "\n"


class ApprovalError(RuntimeError):
    pass


def approve(post_dir: Path, site: Site, by: str, note: str = "") -> dict:
    """A person accepts a post the pipeline stopped on (CORREGIR left after the last round) and publishes it.

    BLOQUEAR is never approvable here: fix the cause and re-run. The override is written into metrics.json."""
    metrics_path = post_dir / "metrics.json"
    if not metrics_path.exists():
        raise ApprovalError(f"{post_dir} has no metrics.json; is it a pipeline post folder?")
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    if not by.strip():
        raise ApprovalError("--by is required: who is accepting the remaining findings?")
    if metrics.get("status") != "needs-human":
        raise ApprovalError(f"status is {metrics.get('status')!r}; only needs-human posts can be approved")
    if not metrics.get("verdict_path") or metrics["verdict_path"][-1] == VERDICT_BLOCK:
        raise ApprovalError(
            "the last verdict is BLOQUEAR (or there is none); fix the cause and re-run the pipeline instead"
        )
    slug = metrics.get("slug", "")
    if not KEBAB.match(slug):
        raise ApprovalError(f"the post has no usable slug ({slug!r})")
    target = site.posts_dir / f"{slug}.md"
    if target.exists():
        raise ApprovalError(f"{target.name} already exists")
    candidate_path, final_path = post_dir / "needs-human.md", post_dir / "final.md"
    if candidate_path.exists():
        final_text = (
            candidate_path.read_text(encoding="utf-8").rstrip("\n") + "\n\n" + FOOTER.format(name=site.data["name"])
        )
    elif (
        final_path.exists()
    ):  # it passed the gate but could not be published (route failure): final.md already has the footer
        final_text = final_path.read_text(encoding="utf-8")
    else:
        raise ApprovalError("neither needs-human.md nor final.md exists in this folder")
    write(final_path, final_text)
    try:
        pages_added = publish(site, slug, final_text)
    except sitefiles.PagesEditError as exc:
        raise ApprovalError(f"could not register the route in clinic.yaml, nothing was published: {exc}") from exc
    metrics["pages_route_added"] = pages_added
    metrics.pop("error", None)
    metrics.update(
        status="published",
        published_to=display_path(target),
        approval={
            "by": by,
            "note": note,
            "on": date.today().isoformat(),
            "overrode": metrics["verdict_path"][-1],
            "remaining": review_remaining(post_dir),
        },
    )
    write(metrics_path, json.dumps(metrics, indent=2, ensure_ascii=False))
    write(post_dir / "pr.md", render_pr(metrics))
    return metrics


def review_remaining(post_dir: Path) -> list[str]:
    files = sorted(post_dir.glob("qa-r[0-9]*.json"))
    if not files:
        return []
    result = json.loads(files[-1].read_text(encoding="utf-8"))
    items = [
        f"{f['rule']}: {f['evidence'][:80]}" for f in result["rules_findings"] if f["severity"] in ("block", "warn")
    ]
    items += [f"model:{f.get('type')}: {str(f.get('quote'))[:80]}" for f in result["model"].get("findings", [])]
    return items
