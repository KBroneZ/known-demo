"""QA stage: run the content-qa-gate (rules, then an optional model review) on a candidate post.

The website generates JSON-LD from frontmatter. So the gate sees what the site will serve, this module renders the
same BlogPosting/FAQPage blocks and the FAQ section into a throwaway "QA view" of the post and checks that.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from qa_gate.findings import VERDICT_BLOCK, VERDICT_FIX, VERDICT_OK, worst_verdict
from qa_gate.gate import check_file
from qa_gate.llm import build_prompt, normalize_finding, run_backend

from .clinicdata import Clinic, Site, parse_post_text
from .sources import load_pool


def faq_section(faq: list) -> str:
    if not faq:
        return ""
    parts = ["## Frequently asked questions", ""]
    for item in faq:
        parts += [f"### {item['question']}", "", item["answer"], ""]
    return "\n".join(parts)


def qa_view(post_file: str, site: Site) -> str:
    post = parse_post_text(post_file)
    fm = post.frontmatter
    base = site.data["website"].rstrip("/")
    url = f"{base}/blog/{fm['slug']}"
    blocks = [
        {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "headline": fm["title"],
            "description": fm["description"],
            "url": url,
            "mainEntityOfPage": url,
            "datePublished": str(fm["date"]),
            "dateModified": str(fm["updated"]),
            "author": {"@type": "Person", "name": fm["author"]},
            "publisher": {"@type": "Dentist", "name": site.data["name"], "url": f"{base}/"},
        }
    ]
    faq = fm.get("faq") or []
    if faq:
        blocks.append(
            {
                "@context": "https://schema.org",
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": f["question"],
                        "acceptedAnswer": {"@type": "Answer", "text": f["answer"]},
                    }
                    for f in faq
                ],
            }
        )
    scripts = "\n".join(
        f'<script type="application/ld+json">\n{json.dumps(b, ensure_ascii=False)}\n</script>' for b in blocks
    )
    body = "\n".join(post.lines[post.frontmatter_end :]).rstrip()
    head = "\n".join(post.lines[: post.frontmatter_end])
    return f"{head}\n{body}\n\n{faq_section(faq)}\n{scripts}\n"


def with_own_route(site: Site, post_file: str) -> Site:
    """The post under review is about to exist: its own /blog/<slug> must count as a page for link and schema checks."""
    slug = parse_post_text(post_file).frontmatter.get("slug")
    pages = list(site.clinic.get("pages") or [])
    if slug and f"/blog/{slug}" not in pages:
        pages.append(f"/blog/{slug}")
    note = (
        f"\n# Reviewer note: /blog/{slug} is the post under review. "
        "It will exist once published; treat it as a valid page.\n"
        f"# Pages that exist on the site: {', '.join(pages)}\n"
    )
    return Site(
        site.id, site.root, Clinic({**site.clinic.data, "pages": pages}, site.clinic.raw_text + note), site.posts
    )


# Model remarks of these types can stop a post (BLOQUEAR). Any other type is an opinion about wording or about how the
# model read the ficha: it is kept as a CORREGIR-level remark so the auto-fix round can act on it.
HARD_MODEL_TYPES = frozenset({"chatbot_residue", "testimonial", "prohibited_promise", "false_medical_claim"})


def apply_block_policy(findings: list[dict]) -> tuple[list[dict], int]:
    out, downgraded = [], 0
    for f in findings:
        if f.get("severity") == "block" and f.get("type") not in HARD_MODEL_TYPES:
            out.append({**f, "severity": "warn", "downgraded_from": "block"})
            downgraded += 1
        else:
            out.append(f)
    return out, downgraded


def model_verdict(findings: list[dict]) -> str:
    severities = {f.get("severity") for f in findings}
    return VERDICT_BLOCK if "block" in severities else VERDICT_FIX if "warn" in severities else VERDICT_OK


def filter_model_findings(findings: list[dict], pool_urls: set[str]) -> tuple[list[dict], int]:
    """Keep the model's block/warn remarks. Severity is normalised first (case, synonyms; an unknown label counts as
    block, it is never dropped). The only thing discarded as noise is 'cannot verify this URL' on a pool URL: the model
    has no browser and the link check already fetched it. Returns (kept findings, number dropped as noise)."""
    kept, dropped = [], 0
    for raw in findings:
        f = normalize_finding(raw)
        if f["severity"] == "info":
            continue
        quote = str(f.get("quote", ""))
        if f.get("type") == "broken_or_fake_source" and any(u in quote for u in pool_urls):
            dropped += 1
            continue
        kept.append(f)
    return kept, dropped


def review(
    post_file: str,
    site: Site,
    work_dir: Path,
    name: str,
    qa_model: str,
    use_model: bool = True,
    offline: bool = False,
    link_cache: dict | None = None,
) -> dict:
    """Run both layers. Returns the report written to qa-<name>.json by the caller."""
    work_dir.mkdir(parents=True, exist_ok=True)
    view_path = work_dir / f"qa-view-{name}.md"
    view_path.write_text(qa_view(post_file, site), encoding="utf-8")
    site = with_own_route(site, post_file)
    t0 = time.perf_counter()
    report, _, post = check_file(view_path, site.clinic, offline=offline, link_cache=link_cache or {})
    rules_seconds = time.perf_counter() - t0
    det_findings = report["findings"]
    result = {
        "name": name,
        "rules_verdict": report["deterministic_verdict"],
        "rules_seconds": round(rules_seconds, 2),
        "rules_findings": det_findings,
        "link_mode": report["link_mode"],
        "model": {"status": "skipped"},
    }
    verdict = report["deterministic_verdict"]
    if use_model:
        prompt = build_prompt(post, site.clinic, det_findings)
        prompt_path = work_dir / f"qa-{name}.prompt.md"
        prompt_path.write_text(prompt, encoding="utf-8")
        t1 = time.perf_counter()
        llm = run_backend("claude", prompt, prompt_path, work_dir / f"qa-{name}.model.txt", qa_model)
        seconds = time.perf_counter() - t1
        if llm.get("status") == "ok":
            pool_urls = {s["url"] for s in load_pool()}
            suggestions = [f for f in llm.get("findings", []) if f.get("kind") == "suggestion"]
            kept, dropped = filter_model_findings(llm.get("findings", []), pool_urls)
            kept, downgraded = apply_block_policy(kept)
            mv, note = model_verdict(kept), llm.get("verdict_note", "")
            said = llm.get("verdict", VERDICT_FIX)
            if not kept and dropped == 0 and said != VERDICT_OK:
                # the model says there is a problem but names nothing we can act on:
                # its verdict stands and a person looks
                mv = worst_verdict(mv, said)
                note = note or f"model said {said} but listed no actionable finding; needs a person"
            if llm.get("verdict_note"):
                mv = worst_verdict(mv, VERDICT_FIX)
            result["model"] = {
                "status": "ok",
                "model": qa_model,
                "cost_usd": llm.get("cost_usd", 0.0),
                "seconds": round(seconds, 1),
                "findings": kept,
                "dropped_unverifiable_url": dropped,
                "downgraded_blocks": downgraded,
                "suggestions": suggestions,
                "verdict": mv,
                "model_said": said,
                "raw_verdict": llm.get("raw_verdict"),
                "note": note,
            }
            if note:
                result["needs_person"] = True
                result["needs_person_reason"] = note
            verdict = worst_verdict(verdict, mv)
        else:  # a model layer that did not run, or whose answer cannot be read, is never a pass: a person looks
            result["model"] = {
                "status": llm.get("status"),
                "detail": llm.get("detail", ""),
                "model": qa_model,
                "seconds": round(seconds, 1),
            }
            result["needs_person"] = True
            result["needs_person_reason"] = f"model review unavailable ({llm.get('status')}); needs a person"
            verdict = worst_verdict(verdict, VERDICT_FIX)
    result["verdict"] = verdict
    return result


def findings_for_fix(result: dict) -> list[dict]:
    out = [f for f in result["rules_findings"] if f["severity"] in ("block", "warn")]
    for f in result["model"].get("findings", []):
        out.append(
            {
                "rule": f"model:{f.get('type', 'other')}",
                "severity": f["severity"],
                "line": 0,
                "evidence": str(f.get("quote", ""))[:160],
                "message": f"{f.get('why', '')} Suggested: {f.get('fix', '')}".strip(),
            }
        )
    return out
