"""Travel rules (b) staleness, (c) unsupported first-hand claims, (d) site.yaml ruleset, (e) links,
and profile wiring."""

from datetime import date

import pytest
from conftest import rules_of

from qa_gate import gate, links, miniyaml, rules_travel
from qa_gate.loader import Clinic, parse_post_text

TODAY = date(2026, 10, 30)
SITE_YAML = """
profile: travel
name: Tripnotes Example
website: https://www.tripnotes.example
required_sections: [Sources]
banned_characters: ["—", "...", "!"]
bylines: [Nora Vale, Theo Marsh]
author_titles: [Editor]
evidence_headings: [How we tested, Methodology]
affiliate:
  hosts: [go.aff.example, booking.example]
  params: [aff_id]
  disclosure_phrases: [affiliate links, may earn a commission]
review_max_age_days: 180
stamp_grace_days: 30
pages: [/, /blog, /blog/lisbon, /blog/porto]
"""
FM = """---
title: "{title}"
description: "A guide."
slug: lisbon
date: {date}
updated: {updated}
author: {author}
category: cities
{extra}---
"""


def site(text: str = SITE_YAML) -> Clinic:
    return Clinic(miniyaml.loads(text), text)


def post(
    body="Body.\n\n## Sources\n\n- <https://www.tripnotes.example/blog/porto>\n",
    title="Lisbon in three days",
    date_="2026-09-20",
    updated="2026-09-20",
    author="Nora Vale",
    extra="",
):
    return parse_post_text(FM.format(title=title, date=date_, updated=updated, author=author, extra=extra) + body)


def run(p, s=None):
    return rules_travel.run(p, s or site(), TODAY)


def test_a_clean_minimal_post_passes_all_travel_rules():
    assert run(post()) == []


# (b) staleness -----------------------------------------------------------------------------------------------


def test_year_in_title_already_past_is_stale():
    assert rules_of(run(post(title="Lisbon in 2025: a guide"))) == ["stale_year_title"]
    assert run(post(title="Lisbon in 2026: a guide")) == []


def test_event_date_already_past_is_stale_but_a_recap_is_not():
    out = run(post("The Wine Fair runs June 16-20, 2026.\n\n## Sources\n\n- x\n"))
    assert rules_of(out) == ["event_date_past"]
    assert run(post("The Wine Fair ran June 16-20, 2026 and was a success.\n\n## Sources\n\n- x\n")) == []
    assert run(post("The Wine Fair runs December 4-6, 2026.\n\n## Sources\n\n- x\n")) == []


def test_year_comes_from_the_paragraph_or_title_when_the_date_has_none():
    out = run(post("The Wine Fair runs June 16-20.\n\n## Sources\n\n- x\n", title="Lisbon in 2026"))
    assert rules_of(out) == ["event_date_past"]
    # no year anywhere: a June date in a post published in September means next June, so it is not past
    assert run(post("The Wine Fair runs June 16-20.\n\n## Sources\n\n- x\n", title="Lisbon")) == []


def test_as_of_and_review_dates_are_not_event_dates():
    body = "Prices checked on June 2, 2026.\n\nLast reviewed June 2, 2026.\n\n## Sources\n\n- Accessed Mar 3, 2026.\n"
    assert "event_date_past" not in rules_of(run(post(body)))


def test_review_stamp_equal_to_publish_date_on_an_old_post():
    body = "Last reviewed August 1, 2026\n\n## Sources\n\n- x\n"
    assert "review_stamp_is_publish_date" in rules_of(run(post(body, date_="2026-08-01", updated="2026-08-01")))
    fresh = run(post("Last reviewed October 20, 2026\n\n## Sources\n\n- x\n", date_="2026-10-20", updated="2026-10-20"))
    assert "review_stamp_is_publish_date" not in rules_of(fresh)  # reviewed 10 days ago: inside the grace period
    fm = run(post(date_="2026-03-01", updated="2026-03-01", extra="last_reviewed: 2026-03-01\n"))
    assert "review_stamp_is_publish_date" in rules_of(fm)


def test_review_older_than_the_limit():
    out = run(post(date_="2026-01-01", updated="2026-02-01", extra="last_reviewed: 2026-03-01\n"))
    assert rules_of(out) == ["review_overdue"]


def test_price_without_as_of_date_and_with_one():
    body = "The Harbor Line ferry costs $12.\n\n## Sources\n\n- x\n"
    assert rules_of(run(post(body))) == ["price_no_as_of"]
    ok = "The Harbor Line ferry costs $12 (prices checked September 2026).\n\n## Sources\n\n- x\n"
    assert run(post(ok)) == []
    assert run(post(body, extra="prices_as_of: 2026-09-15\n")) == []


def test_old_as_of_date_is_flagged():
    body = "Prices as of January 2026. The Harbor Line ferry costs $12.\n\n## Sources\n\n- x\n"
    assert rules_of(run(post(body))) == ["price_as_of_old"]


# (c) first-hand claims -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "We tested every hostel in town.",
        "Our editors verified each fare on May 22.",
        "We personally tried the tram.",
        "Editor's verification: all prices were cross-checked.",
        "I stayed at the Hotel Aurora for a week.",
    ],
)
def test_first_hand_claim_without_evidence_block_is_flagged(text):
    out = run(post(f"{text}\n\n## Sources\n\n- x\n"))
    assert "unsupported_first_hand_claim" in rules_of(out)


def test_title_claims_are_read_too():
    assert "unsupported_first_hand_claim" in rules_of(run(post(title="Best eSIMs, tested across 10 countries")))


def test_evidence_block_makes_the_claim_acceptable():
    evidence = (
        "## How we tested\n\n"
        + "We bought each plan on a named date, ran the speed test twice in each city and kept the receipts. " * 2
        + "\n\n"
    )
    out = run(post("We tested every plan.\n\n" + evidence + "## Sources\n\n- x\n"))
    assert "unsupported_first_hand_claim" not in rules_of(out)
    stub = run(post("We tested every plan.\n\n## How we tested\n\nTrust us.\n\n## Sources\n\n- x\n"))
    assert "unsupported_first_hand_claim" in rules_of(stub)


@pytest.mark.parametrize(
    "text",
    [
        "Battle-tested itineraries are overrated.",
        "The test results of the lab were published.",
        "We haven't tested it, so check first.",
        "Testing by The Gone Goat found the plan slow.",
        "Readers tried this route and liked it.",
    ],
)
def test_not_a_claim_of_the_site(text):
    assert "unsupported_first_hand_claim" not in rules_of(run(post(f"{text}\n\n## Sources\n\n- x\n")))


# (d) ruleset ---------------------------------------------------------------------------------------------------


def test_missing_required_section_is_blocked():
    out = run(post("Body only.\n"))
    assert rules_of(out) == ["missing_required_section"] and out[0].severity == "block"
    assert run(post("Body.\n\n### Sources\n\n- x\n")) == []  # any heading level


def test_banned_characters_are_flagged_once_per_line_per_character():
    out = run(post("A — B — C! Wait... what!\n\n## Sources\n\n- x\n"))
    assert rules_of(out) == ["banned_character"] * 3
    assert {f.evidence for f in out} == {"—", "!", "..."}


def test_banned_characters_inside_code_or_links_are_left_alone():
    assert (
        run(
            post(
                "See [the post](https://www.tripnotes.example/blog/porto?x=!).\n\n```\na — b!\n```\n\n## Sources\n\n- "
                "x\n"
            )
        )
        == []
    )


def test_affiliate_link_needs_a_disclosure():
    body = "Book via [the partner](https://go.aff.example/abc).\n\n## Sources\n\n- x\n"
    out = run(post(body))
    assert "affiliate_disclosure_missing" in rules_of(out)
    assert [f.severity for f in out if f.rule == "affiliate_disclosure_missing"] == ["block"]
    ok = body + "\nThis post contains affiliate links.\n"
    assert "affiliate_disclosure_missing" not in rules_of(run(post(ok)))
    by_param = "Book via [Hotel](https://stay.example/room?aff_id=77).\n\n## Sources\n\n- x\n"
    assert "affiliate_disclosure_missing" in rules_of(run(post(by_param)))


def test_disclosure_without_affiliate_links_is_fine():
    assert run(post("This post contains affiliate links.\n\n## Sources\n\n- x\n")) == []


def test_byline_must_be_on_the_list_and_title_allowed():
    out = run(post(author="Rae Nobody"))
    assert rules_of(out) == ["byline_not_allowed"] and out[0].severity == "block"
    assert run(post(author="Theo Marsh")) == []
    assert rules_of(run(post(extra="author_title: Senior Travel Editor\n"))) == ["byline_title_not_allowed"]
    assert run(post(extra="author_title: Editor\n")) == []


def test_frontmatter_must_be_complete():
    p = parse_post_text('---\ntitle: "x"\n---\nBody.\n\n## Sources\n\n- x\n')
    out = run(p)
    assert "frontmatter_missing_field" in rules_of(out)
    assert "frontmatter_invalid" in rules_of(run(parse_post_text("No frontmatter\n\n## Sources\n\n- x\n")))


def test_optional_keys_missing_from_site_yaml_turn_rules_off():
    bare = site("profile: travel\nname: Bare\nwebsite: https://bare.example\npages: [/]\n")
    p = post("A — B! Book via [the partner](https://go.aff.example/abc).\n", author="Anyone")
    assert run(p, bare) == []


# (e) links -----------------------------------------------------------------------------------------------------


def test_403_and_other_anti_bot_answers_are_inconclusive_never_dead(monkeypatch):
    s = site()
    for status in (401, 403, 429, 451):
        f = links.classify_travel(3, "https://x.example/a", {"status": status})
        assert f.rule == "link_blocked" and f.severity == "warn", status
    assert links.classify_travel(3, "https://x.example/a", {"status": 404}).rule == "link_broken"
    assert links.classify_travel(3, "https://x.example/a", {"error": "nxdomain"}).rule == "link_broken"
    assert links.classify_travel(3, "https://x.example/a", {"status": 200, "final": "https://x.example/a"}) is None
    assert s.get("profile") == "travel"


def test_a_link_that_moved_to_another_domain_is_a_warning():
    f = links.classify_travel(3, "https://old.example/a/b", {"status": 200, "final": "https://www.new.example/a/b"})
    assert f.rule == "link_moved_domain" and f.severity == "warn"
    assert links.classify_travel(3, "http://a.example/a", {"status": 200, "final": "https://www.a.example/a/"}) is None
    assert links.classify_travel(3, "https://a.co.uk/x", {"status": 200, "final": "https://www.a.co.uk/x"}) is None


def test_dental_profile_still_uses_link_unverifiable_for_403():
    assert links.classify(3, "https://x.example/a", {"status": 403}).rule == "link_unverifiable"


def test_internal_links_use_the_site_page_list():
    cache = {}
    p = post("See [Porto](/blog/porto) and [Faro](/blog/faro).\n\n## Sources\n\n- x\n")
    findings, _ = links.check_links(p, site(), True, cache)
    assert [(f.rule, f.evidence) for f in findings] == [("link_broken_internal", "/blog/faro")]


# profile wiring ------------------------------------------------------------------------------------------------


def test_gate_routes_travel_sites_to_the_travel_rules_and_skips_dental_ones(tmp_path):
    body = (
        "Book via [the partner](https://go.aff.example/abc). Call (512) 555-0187. The Rail Pass costs $12 and Dr. Zed "
        "saw it.\n\n"
        "## Sources\n\n- x\n"
    )
    p = post(body)
    findings, _ = gate.run_deterministic(p, site(), offline=True, link_cache={}, today=TODAY)
    names = rules_of(findings)
    assert "affiliate_disclosure_missing" in names
    assert (
        "nap_phone_mismatch" not in names and "dentist_not_in_roster" not in names and "price_not_in_ficha" not in names
    )
    assert "chatbot_residue" not in names


def test_gate_still_catches_chatbot_residue_and_ai_phrases_in_travel_posts():
    p = post("In today's fast-paced world, travel is great. I hope this helps!\n\n## Sources\n\n- x\n")
    findings, _ = gate.run_deterministic(p, site(), offline=True, link_cache={}, today=TODAY)
    assert {"ai_phrase", "chatbot_residue"} <= set(rules_of(findings))
