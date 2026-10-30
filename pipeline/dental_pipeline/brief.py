"""Brief stage: everything the writer is allowed to use, built from data, not from the model."""

from __future__ import annotations

from .clinicdata import Site, facts_block, slugify
from .sources import load_pool, pick_sources
from .topics import Candidate

WORD_RANGE = "about 600 to 850 words (length follows the content; it is not a target)"


def pick_authors(site: Site, service: dict | None) -> tuple[str, str]:
    """(author, reviewer). The dentist whose bio says they review the site's clinical content is the reviewer
    of record; the author is another dentist. Without such a bio, the service's lead dentist writes and the
    other reviews."""
    dentists = site.data["dentists"]
    names = [d["name"] for d in dentists]
    reviewer = next((d["name"] for d in dentists if "reviews the clinical" in d.get("bio", "")), None)
    if reviewer:
        author = next((n for n in names if n != reviewer), reviewer)
        return author, reviewer
    lead = (service or {}).get("lead_dentist")
    author = lead if lead in names else names[0]
    return author, next((n for n in names if n != author), author)


def internal_links(site: Site, service: dict | None, limit_posts: int = 1) -> list[dict]:
    links = []
    if service and service.get("slug"):
        links.append({"url": f"/services/{service['slug']}", "why": f"the {service['name']} service page"})
    links.append({"url": "/contact", "why": "booking and contact"})
    links.append({"url": "/team", "why": "the dentists"})
    for slug, fm in list(site.posts.items())[:limit_posts]:
        links.append({"url": f"/blog/{slug}", "why": f"related post: {fm.get('title', slug)}"})
    return links


def build_brief(site: Site, cand: Candidate, extra_sources: int = 3) -> dict:
    service = next(s for s in site.data["services"] if s["name"] == cand.service)
    author, reviewer = pick_authors(site, service)
    keywords = [cand.keyword, cand.service.lower(), *service.get("aliases", [])[:3]]
    pool = load_pool()
    sources = pick_sources(keywords, pool, extra_sources) or pick_sources(cand.question.lower().split(), pool, 2)
    questions = [cand.question] + [f["question"] for f in service.get("faq", [])]
    n = site.data["nap"]
    return {
        "clinic_id": site.id,
        "clinic_name": site.data["name"],
        "topic": {
            "question": cand.question,
            "source": cand.source,
            "source_id": cand.source_id,
            "comments": cand.comments,
            "retrieved": cand.retrieved,
            "intent": cand.intent,
            "patient_wording": cand.patient_wording,
        },
        "service": cand.service,
        "service_slug": service.get("slug"),
        "service_summary": service.get("summary", ""),
        "service_text": [*service.get("body", []), *[f"{f['question']} {f['answer']}" for f in service.get("faq", [])]],
        "primary_keyword": f"{cand.keyword} {n['city']}".lower(),
        "keyword_note": "heuristic: service alias + city; no search-volume data was consulted",
        "intent": "informational; a local patient researching before booking",
        "questions": questions,
        "related_questions": list(cand.related[:2]),
        "author": author,
        "reviewer": reviewer,
        "category": slugify(cand.service),
        "internal_links": internal_links(site, service),
        "sources": [{"url": s["url"], "publisher": s["publisher"], "covers": s["covers"]} for s in sources],
        "word_range": WORD_RANGE,
        "facts": facts_block(site),
    }


def render_markdown(brief: dict) -> str:
    out = [
        f"# Brief: {brief['topic']['question']}",
        "",
        f"- Clinic: {brief['clinic_name']} ({brief['clinic_id']})",
        f"- Service: {brief['service']}"
        + (f" (page /services/{brief['service_slug']})" if brief["service_slug"] else ""),
        f"- Primary keyword: {brief['primary_keyword']} ({brief['keyword_note']})",
        f"- Intent: {brief['intent']}"
        + (f" (search-style intent: {brief['topic']['intent']})" if brief["topic"]["intent"] else ""),
        f"- Topic source: {brief['topic']['source']} {brief['topic']['source_id']}, "
        f"{brief['topic']['comments']} comments, retrieved {brief['topic']['retrieved']}",
        *(
            [f"- How a patient put it: {brief['topic']['patient_wording']!r}"]
            if brief["topic"]["patient_wording"]
            else []
        ),
        f"- Author / clinical reviewer: {brief['author']} / {brief['reviewer']}",
        f"- Length: {brief['word_range']}",
        "",
        "## Questions the post must answer",
        "",
    ]
    out += [f"{i}. {q}" for i, q in enumerate(brief["questions"], 1)]
    if brief["related_questions"]:
        out += ["", "Other questions real patients asked about this (answer them only where they fit naturally):", ""]
        out += [f"- {q}" for q in brief["related_questions"]]
    out += ["", "## Facts about the clinic (the only ones allowed)", "", brief["facts"]]
    if brief["service_summary"]:
        out += ["", f"Service summary from clinic.yaml: {brief['service_summary']}"]
    if brief["service_text"]:
        out += [
            "",
            "What the clinic itself says about this service "
            "(the only claims about how the clinic works that you may make; keep their conditions):",
            "",
        ]
        out += [f"- {t}" for t in brief["service_text"]]
    out += ["", "## Internal links you may use (root-relative, pick 2 or 3)", ""]
    out += [f"- `{link['url']}`: {link['why']}" for link in brief["internal_links"]]
    out += ["", "## Authorized external sources (use ONLY these URLs, in the paragraph they support)", ""]
    if brief["sources"]:
        out += [f"- <{s['url']}>: {s['publisher']}; covers {', '.join(s['covers'])}" for s in brief["sources"]]
    else:
        out += ["- none for this topic: link to nothing external and state no statistic, percentage or study"]
    return "\n".join(out) + "\n"
