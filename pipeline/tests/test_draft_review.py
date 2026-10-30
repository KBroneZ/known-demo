import json
from datetime import date

import pytest
from sample import GOOD, cand

from dental_pipeline import brief, draft, review
from dental_pipeline.clinicdata import QA_ROOT
from qa_gate import links


def test_parse_assemble_roundtrip(site_a):
    b = brief.build_brief(site_a, cand())
    parsed = draft.parse_answer("```markdown\n" + GOOD + "```")
    assert parsed.title.startswith("Is Professional") and len(parsed.faq) == 1
    slug = draft.unique_slug(parsed.title, set())
    text = draft.assemble(parsed, b, slug, date(2026, 10, 30))
    fm = draft.parse_post_text(text).frontmatter
    assert fm["slug"] == slug and fm["date"] == "2026-10-30" == fm["updated"]
    assert fm["author"] == b["author"] and fm["reviewed_by"] == b["reviewer"] and fm["service"] == "teeth-whitening"
    assert draft.parse_answer(text).faq == parsed.faq


def test_model_cannot_choose_author_or_date(site_a):
    b = brief.build_brief(site_a, cand())
    sneaky = GOOD.replace("faq:", "author: Dr. Nobody\ndate: 1999-01-01\nfaq:")
    text = draft.assemble(draft.parse_answer(sneaky), b, "x-slug", date(2026, 10, 30))
    fm = draft.parse_post_text(text).frontmatter
    assert fm["author"] == b["author"] and fm["date"] == "2026-10-30"


def test_validation_mirrors_the_site_schema():
    ok = draft.parse_answer(GOOD)
    assert draft.validate(ok) == []
    bad = draft.Parsed("Short", "tiny", (("Q?", "short"),), "# H1 title\nfew words")
    problems = " ".join(draft.validate(bad))
    assert "title length" in problems and "description length" in problems and "faq entry" in problems
    assert "too short" in problems and "starts with a #" in problems


def test_unique_slug_avoids_collisions():
    assert draft.unique_slug("Is Teeth Whitening Safe?", {"teeth-whitening-safe"}) == "teeth-whitening-safe-2"
    assert len(draft.unique_slug("x " * 80, set())) <= 60


def test_unparseable_answer_raises():
    with pytest.raises(draft.DraftError):
        draft.parse_answer("no frontmatter here, just chat")


def test_qa_view_adds_matching_json_ld_and_faq_section(site_a):
    b = brief.build_brief(site_a, cand())
    text = draft.assemble(draft.parse_answer(GOOD), b, "whitening-sensitive-teeth", date(2026, 10, 30))
    view = review.qa_view(text, site_a)
    assert view.count("application/ld+json") == 2
    assert "## Frequently asked questions" in view and "Can sensitive teeth be whitened?" in view
    ld = json.loads(view.split('<script type="application/ld+json">\n')[1].split("\n</script>")[0])
    assert ld["headline"] == "Is Professional Teeth Whitening Safe for Sensitive Teeth?"
    assert ld["url"].endswith("/blog/whitening-sensitive-teeth")


def test_rules_pass_a_clean_draft_and_block_a_bad_one(site_a, tmp_path):
    b = brief.build_brief(site_a, cand())
    cache = links.load_cache(QA_ROOT / "fixtures" / "link-cache.json")
    ok = draft.assemble(draft.parse_answer(GOOD), b, "whitening-sensitive-teeth", date.today())
    r = review.review(ok, site_a, tmp_path, "r0", "haiku", use_model=False, offline=True, link_cache=cache)
    assert r["verdict"] == "PUBLICAR", r["rules_findings"]
    bad = ok.replace("Whitening is usually safe", "We guarantee whitening is safe, call (512) 555-0187")
    r = review.review(bad, site_a, tmp_path, "r1", "haiku", use_model=False, offline=True, link_cache=cache)
    assert r["verdict"] == "BLOQUEAR"
    assert {f["rule"] for f in r["rules_findings"]} >= {"prohibited_promise", "nap_phone_mismatch"}


def test_existing_site_posts_pass_the_rules_through_the_qa_view(site_a, site_b, tmp_path):
    cache = links.load_cache(QA_ROOT / "fixtures" / "link-cache.json")
    for site in (site_a,):
        for slug in (
            "dental-emergency-austin",
            "dental-implants-vs-bridges",
            "how-often-dental-cleaning",
        ):  # the original posts
            text = (site.posts_dir / f"{slug}.md").read_text(encoding="utf-8")
            r = review.review(text, site, tmp_path, slug[:12], "haiku", use_model=False, offline=True, link_cache=cache)
            assert r["verdict"] == "PUBLICAR", (slug, r["rules_findings"])


def test_model_noise_about_pool_urls_is_dropped():
    findings = [
        {
            "severity": "warn",
            "type": "broken_or_fake_source",
            "quote": "[x](https://www.mouthhealthy.org/all-topics-a-z/bridges)",
        },
        {"severity": "warn", "type": "broken_or_fake_source", "quote": "[x](https://example.org/made-up)"},
        {"severity": "info", "type": "other", "quote": "meh"},
        {"severity": "block", "type": "false_medical_claim", "quote": "scrub it"},
    ]
    kept, dropped = review.filter_model_findings(findings, {"https://www.mouthhealthy.org/all-topics-a-z/bridges"})
    assert dropped == 1 and [f["quote"][:13] for f in kept] == ["[x](https://e", "scrub it"]
    assert review.model_verdict(kept) == "BLOQUEAR" and review.model_verdict([]) == "PUBLICAR"


def test_findings_for_fix_merges_rules_and_model():
    result = {
        "rules_findings": [
            {"rule": "ai_phrase", "severity": "warn", "line": 9, "evidence": "delve", "message": "m"},
            {"rule": "link_unverified", "severity": "info", "line": 3, "evidence": "u", "message": "m"},
        ],
        "model": {
            "findings": [
                {"type": "unsourced_claim", "severity": "warn", "quote": "most people", "why": "w", "fix": "f"}
            ]
        },
    }
    out = review.findings_for_fix(result)
    assert [f["rule"] for f in out] == ["ai_phrase", "model:unsourced_claim"]


def test_block_policy_downgrades_opinion_blocks_but_keeps_hard_types():
    findings = [
        {"severity": "block", "type": "fact_vs_ficha", "quote": "reviewed_by: x"},
        {"severity": "block", "type": "false_medical_claim", "quote": "scrub it"},
        {"severity": "block", "type": "chatbot_residue", "quote": "As an AI"},
        {"severity": "warn", "type": "unsourced_claim", "quote": "most people"},
    ]
    out, downgraded = review.apply_block_policy(findings)
    assert downgraded == 1
    assert [f["severity"] for f in out] == ["warn", "block", "block", "warn"]
    assert out[0]["downgraded_from"] == "block"
    assert review.model_verdict(out) == "BLOQUEAR"
    assert review.model_verdict([out[0], out[3]]) == "CORREGIR"


def test_own_route_counts_as_a_page(site_a):
    b = brief.build_brief(site_a, cand())
    text = draft.assemble(draft.parse_answer(GOOD), b, "brand-new-slug", date(2026, 10, 30))
    site = review.with_own_route(site_a, text)
    assert "/blog/brand-new-slug" in site.clinic.get("pages")
    assert "/blog/brand-new-slug" not in site_a.clinic.get("pages")
    assert "Reviewer note" in site.clinic.raw_text


def test_reviewer_of_record_follows_the_bios(site_a, site_b):
    assert brief.pick_authors(site_a, None) == ("Dr. Marcus Oyelaran", "Dr. Elena Marsh")
    assert brief.pick_authors(site_b, None) == ("Dr. Tomas Alvarez", "Dr. Priya Raman")
