"""Run the deterministic layer on one post and build its report."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from . import links, rules_content, rules_facts, rules_structure, rules_travel
from .findings import SEVERITY_RANK, Finding, verdict_for
from .loader import Clinic, Post, load_post
from .paths import display_path


def run_deterministic(
    post: Post,
    clinic: Clinic,
    offline: bool = False,
    link_cache: dict | None = None,
    timeout: float = links.DEFAULT_TIMEOUT,
    max_age_days: int | None = links.CACHE_MAX_AGE_DAYS,
    today: date | None = None,
) -> tuple[list[Finding], dict]:
    findings: list[Finding] = []
    if rules_travel.is_travel(clinic):
        findings += rules_travel.run(post, clinic, today)
        findings += rules_content.run_generic(post, clinic)
    else:
        findings += rules_structure.run(post, clinic)
        findings += rules_facts.run(post, clinic)
        findings += rules_content.run(post, clinic)
    link_findings, fresh = links.check_links(post, clinic, offline, link_cache, timeout, max_age_days)
    findings += link_findings
    findings.sort(key=lambda f: (f.line, -SEVERITY_RANK[f.severity], f.rule))
    return findings, fresh


def build_report(post: Post, findings: list[Finding], offline: bool) -> dict:
    counts = {s: sum(1 for f in findings if f.severity == s) for s in SEVERITY_RANK}
    return {
        "post": post.name,
        "file": display_path(post.path),
        "verdict": verdict_for(findings),
        "deterministic_verdict": verdict_for(findings),
        "link_mode": "offline-cache" if offline else "online",
        "counts": counts,
        "findings": [f.to_dict() for f in findings],
        "llm": {"status": "not-run"},
    }


def check_file(
    path: str | Path,
    clinic: Clinic,
    offline: bool = False,
    link_cache: dict | None = None,
    timeout: float = links.DEFAULT_TIMEOUT,
    max_age_days: int | None = links.CACHE_MAX_AGE_DAYS,
    today: date | None = None,
) -> tuple[dict, dict, Post]:
    post = load_post(path)
    findings, fresh = run_deterministic(post, clinic, offline, link_cache, timeout, max_age_days, today)
    return build_report(post, findings, offline), fresh, post


def internal_error_report(path: str | Path, exc: Exception, offline: bool) -> dict:
    """A crash while checking a post fails closed: BLOQUEAR with a gate_internal_error finding."""
    finding = Finding(
        "gate_internal_error",
        "block",
        0,
        f"{type(exc).__name__}: {exc}"[:200],
        "The gate crashed on this post; treat it as not reviewed.",
    )
    post = Post(Path(path), {}, None, (), (), ())
    return build_report(post, [finding], offline)
