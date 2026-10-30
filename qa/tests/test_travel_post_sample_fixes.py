"""Changes made after the first run on real posts (README: 'post-sample'). General behaviour, not those posts."""

import io
import urllib.error
from datetime import date

from conftest import rules_of
from test_travel_site_rules import post, run, site

from qa_gate import links
from qa_gate import rules_travel_consistency as rc
from qa_gate.loader import parse_post_text

FM = '---\ntitle: "x"\nslug: a\ndate: 2026-05-01\nupdated: 2026-05-01\nauthor: Nora Vale\ncategory: c\n---\n'


def test_table_rows_that_share_a_category_tag_are_different_products():
    body = (
        "| River Deck (Opening Day) | £600-£1,200 | Lounge |\n| Garden Terrace (Opening Day) | £700-£1,400 | Garden |\n"
        "| Royal Pavilion (Royal Enclosure) | £2,500-£4,500 | Dining |\n| Royal Box (Royal Enclosure) | £3,500-£5,500 "
        "| Box |\n"
    )
    assert rc.run(parse_post_text(FM + body), None, date(2026, 10, 30)) == []


def test_the_same_named_row_with_two_prices_is_still_a_conflict():
    body = (
        "| River Deck (Opening Day) | £600-£1,200 | Lounge |\n\n"
        "The River Deck (Opening Day) package is £700-£1,400 online.\n"
    )
    assert rules_of(rc.run(parse_post_text(FM + body), None, date(2026, 10, 30))) == ["numeric_inconsistency"]


def test_a_headline_quoted_in_the_sources_list_is_not_a_claim_of_the_site():
    body = "Plain text.\n\n## Sources\n\n- Monito Airalo vs Holafly We Tested Them in 11 Countries: [x](https://m.example/a)\n"
    assert "unsupported_first_hand_claim" not in rules_of(run(post(body)))
    assert "unsupported_first_hand_claim" in rules_of(
        run(post("We tested them in 11 countries.\n\n## Sources\n\n- x\n"))
    )


def test_affiliate_short_links_may_land_on_the_front_page():
    s = site()
    p = post(
        "Book via [the partner](https://booking.example/x/y) or see [a page](https://other.example/a/b).\n\n"
        "## Sources\n\n- x\n"
    )
    cache = {
        u: {"status": 200, "final": "https://www.merchant.example/?tag=1", "checked": "2026-10-30"}
        for u in ("https://booking.example/x/y", "https://other.example/a/b")
    }
    found = links.check_links(p, s, True, cache, max_age_days=None)[0]
    assert [(f.rule, f.evidence) for f in found] == [("link_redirects_home", "https://other.example/a/b")]


def test_a_blocked_answer_from_another_domain_is_reported_as_moved_and_unconfirmed():
    f = links.classify_travel(3, "https://old.example/a", {"status": 403, "final": "https://www.new.example/a"})
    assert f.rule == "link_moved_domain" and f.severity == "warn" and "403" in f.message
    assert (
        links.classify_travel(3, "https://x.example/a", {"status": 403, "final": "https://www.x.example/a"}).rule
        == "link_blocked"
    )


def test_http_errors_keep_the_final_address(monkeypatch):
    def fake_urlopen(req, timeout=0):
        raise urllib.error.HTTPError("https://new.example/a", 403, "Forbidden", {}, io.BytesIO(b""))

    monkeypatch.setattr(links.urllib.request, "urlopen", fake_urlopen)
    assert links._fetch_once("https://old.example/a", 1) == {"status": 403, "final": "https://new.example/a"}


def test_site_can_require_the_disclosure_footer_on_every_post_even_without_affiliate_links():
    from qa_gate import miniyaml
    from qa_gate.loader import Clinic

    text = (
        "profile: travel\nname: S\nwebsite: https://s.example\naffiliate:\n  hosts: [booking.example]\n  "
        "disclosure_phrases: [affiliate links]\n  disclosure_on_every_post: true\npages: [/]\n"
    )
    strict = Clinic(miniyaml.loads(text), text)
    plain = post("No links here.\n\n## Sources\n\n- x\n")
    assert rules_of(run(plain, strict)) == ["affiliate_disclosure_missing"]
    assert run(post("No links here. This post contains affiliate links.\n\n## Sources\n\n- x\n"), strict) == []
    assert run(plain) == []  # the default only asks for it when an affiliate link is present
