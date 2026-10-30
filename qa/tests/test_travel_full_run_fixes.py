"""Changes made after the full run on a real travel blog (README: 'full run'). Each test states a general behaviour that
a precision audit of the findings showed was wrong; the sentences are invented, none comes from a real site."""

from datetime import date

from conftest import rules_of
from test_travel_site_rules import post, run, site

from qa_gate import links, rules_content
from qa_gate import rules_travel_consistency as rc
from qa_gate import rules_travel_fresh as fresh
from qa_gate.loader import parse_post_text
from qa_gate.travel_text import entity_phrases, quantities

TODAY = date(2026, 10, 30)
FM = '---\ntitle: "x"\nslug: a\ndate: 2026-05-01\nupdated: 2026-05-01\nauthor: Nora Vale\ncategory: c\n---\n'
PARA = chr(10) * 2
SOURCES = "\n\n## Sources\n\n- x\n"


def generic(body: str):
    return rules_content.run_generic(parse_post_text(FM + body), site())


# --- chatbot residue ------------------------------------------------------------------------------------------


def test_describing_a_product_as_an_ai_tool_is_not_chatbot_residue():
    assert "chatbot_residue" not in rules_of(generic("Zephyr positions itself as an AI travel planner for families."))
    assert "chatbot_residue" not in rules_of(generic("The app is built as an AI agent that books flights."))


def test_real_chatbot_residue_is_still_blocked():
    for text in (
        "As an AI language model, I cannot browse.",
        "As an AI assistant I can help.",
        "As an AI, I cannot say.",
    ):
        assert "chatbot_residue" in rules_of(generic(text)), text


# --- placeholders ---------------------------------------------------------------------------------------------


def test_bracket_slots_inside_a_quoted_template_are_not_placeholders():
    body = 'Try this prompt: "Plan 5 days in [city] for [number] people with a budget of $[amount]."'
    assert "placeholder" not in rules_of(generic(body))
    assert "placeholder" in rules_of(generic("Plan 5 days in [city] for two."))


def test_tbd_as_a_status_word_in_a_sentence_is_not_a_placeholder_but_a_bare_tbd_is():
    assert "placeholder" not in rules_of(generic("The first sailings are still TBD, says the line."))
    assert "placeholder" in rules_of(generic("TBD"))
    assert "placeholder" in rules_of(generic("| Price | TBD |"))
    assert "placeholder" in rules_of(generic("The price is [TBD] for now."))
    assert "placeholder" in rules_of(generic("TODO: add the price."))


# --- first-hand claims ----------------------------------------------------------------------------------------


def test_a_cited_headline_or_a_quote_or_a_question_is_not_a_first_hand_claim():
    cases = [
        "Kill switches held up (source: Acme VPN Do Kill Switches Work We Tested 30 VPNs, Example News 2026).",
        "Sources: Acme VPN Do Kill Switches Work We Tested 30 VPNs, Example News 2026.",
        'Ask the bot: "What if I booked directly with the hotel instead?"',
        "Can I buy cover after I have already booked the surgery?",
        'The slogan goes from "I have a weekend" to "I have a booked flight" in one tap.',
    ]
    for text in cases:
        assert "unsupported_first_hand_claim" not in rules_of(run(post(text + SOURCES))), text


def test_a_plain_first_hand_claim_is_still_found():
    assert "unsupported_first_hand_claim" in rules_of(run(post("We tested 30 VPNs in 12 cities." + SOURCES)))
    assert "unsupported_first_hand_claim" in rules_of(run(post("I booked three flights to compare." + SOURCES)))


# --- AI phrases ------------------------------------------------------------------------------------------------


def test_an_ai_phrase_inside_a_cited_title_is_not_flagged():
    body = "Reviews are mixed (source: Acme Tours review, the ultimate guide to skip-the-line)."
    assert "ai_phrase" not in rules_of(generic(body))
    assert "ai_phrase" in rules_of(generic("This is the ultimate guide to skip-the-line."))


# --- event dates -----------------------------------------------------------------------------------------------


def test_a_date_from_an_earlier_year_than_the_post_is_history_not_a_stale_event():
    p = post(
        "An eclipse like the one on July 22, 2009 is rare. The fair opens July 6-12, 2026." + SOURCES,
        date_="2026-05-01",
    )
    found = [(f.rule, f.evidence) for f in fresh.check_event_dates(p, TODAY)]
    assert found == [("event_date_past", "July 6-12, 2026")]


def test_a_date_inside_a_source_citation_or_a_verification_stamp_is_not_an_event():
    cited = "Prices rose (source: Example News, March 3, 2026)." + SOURCES
    assert fresh.check_event_dates(post(cited, date_="2026-08-27"), TODAY) == []
    stamp = "Editorial verification May 23, 2026." + SOURCES
    assert fresh.check_event_dates(post(stamp, date_="2026-05-20"), TODAY) == []
    assert rules_of(fresh.check_event_dates(post("The fair is on May 23, 2026." + SOURCES, date_="2026-05-20"), TODAY))


# --- price as-of dates -----------------------------------------------------------------------------------------


def test_an_as_of_date_that_is_not_about_prices_does_not_date_the_prices():
    body = "Tags are allowed in luggage as of December 2022." + PARA + "The tag costs $29." + SOURCES
    found = rules_of(fresh.check_prices_dated(post(body), site(), TODAY))
    assert found == ["price_no_as_of"]


def test_an_as_of_date_next_to_a_price_still_counts():
    body = "The tag costs $29 as of December 2022." + SOURCES
    assert rules_of(fresh.check_prices_dated(post(body), site(), TODAY)) == ["price_as_of_old"]
    assert (
        fresh.check_prices_dated(post("Prices checked October 2026. The tag costs $29." + SOURCES), site(), TODAY) == []
    )


# --- links -----------------------------------------------------------------------------------------------------


def test_an_affiliate_short_link_that_ends_on_another_domain_is_not_a_moved_site():
    s = site()
    p = post("Book via [the partner](https://go.aff.example/abc) or see [a page](https://old.example/a)." + SOURCES)
    cache = {
        "https://go.aff.example/abc": {"status": 403, "final": "https://www.merchant.example/?tag=1", "checked": "x"},
        "https://old.example/a": {"status": 403, "final": "https://www.new.example/a", "checked": "x"},
    }
    found = links.check_links(p, s, True, cache, max_age_days=None)[0]
    assert [(f.rule, f.evidence) for f in found] == [("link_moved_domain", "https://old.example/a")]


def test_a_language_root_that_redirects_to_the_site_root_is_not_a_soft_404():
    s = site()
    for deep in ("https://clinic.example/en/", "https://clinic.example/en-us", "https://clinic.example/fr/"):
        assert links.classify_travel(3, deep, {"status": 200, "final": "https://clinic.example/"}) is None, deep
    deep_page = links.classify_travel(
        3, "https://clinic.example/en/prices", {"status": 200, "final": "https://clinic.example/"}
    )
    assert deep_page.rule == "link_redirects_home"
    assert s  # site fixture unused otherwise


def test_redirect_endpoints_declared_in_site_yaml_are_not_missing_pages():
    text = (
        "profile: travel\nname: S\nwebsite: https://www.tripnotes.example\nredirect_prefixes: [/go/]\n"
        "pages: [/, /blog/lisbon]\n"
    )
    from qa_gate import miniyaml
    from qa_gate.loader import Clinic

    declared = Clinic(miniyaml.loads(text), text)
    p = post("[Book here](/go/hotel) or [read more](/blog/missing)." + SOURCES)
    found = links.check_links(p, declared, True, {}, max_age_days=None)[0]
    assert [(f.rule, f.evidence) for f in found] == [("link_broken_internal", "/blog/missing")]
    undeclared = links.check_links(p, site(), True, {}, max_age_days=None)[0]
    assert sorted(f.evidence for f in undeclared) == ["/blog/missing", "/go/hotel"]


# --- consistency -----------------------------------------------------------------------------------------------


def test_status_flags_acronyms_and_single_letters_are_not_named_entities():
    names = [
        name for _, _, name in entity_phrases("Ticket (SOLD OUT) in the US and TX with a 3T scanner at Port Alba.")
    ]
    assert "sold out" not in names and "us" not in names and "tx" not in names and "t" not in names
    assert "port alba" in names


def test_a_monthly_rate_and_a_one_off_price_are_different_quantities():
    assert quantities("$50/month")[0].unit != quantities("$400")[0].unit
    assert quantities("$50 per month")[0].unit == quantities("$50/month")[0].unit
    body = "The Harbor Pass is $50/month with the app.\n\nThe Harbor Pass costs $400 up front.\n"
    assert rc.run(parse_post_text(FM + body), None, TODAY) == []


def test_a_per_year_figure_and_a_ten_year_total_are_different_quantities():
    body = "The Harbor Club costs $35K per year in dues.\n\nThe Harbor Club costs $400,000 over 10 years in dues.\n"
    assert rc.run(parse_post_text(FM + body), None, TODAY) == []
    plain = "The Harbor Club costs $35K in dues.\n\nThe Harbor Club costs $400,000 in dues.\n"
    assert rules_of(rc.run(parse_post_text(FM + plain), None, TODAY)) == ["numeric_inconsistency"]


# --- second wave: fixed against the second audit sample ---------------------------------------------------------


def test_tier_suffixes_make_a_different_product_not_the_same_entity():
    assert not rc.same_entity("airline pass standard", "airline pass standard plus")
    assert not rc.same_entity("scan pro", "scan pro max")
    assert rc.same_entity("donau licht", "donau licht boats")


def test_a_date_next_to_a_reporting_or_past_tense_verb_is_history():
    for text in (
        "The May 20, 2026 chart changes affected 136 hotels.",
        "Only 8% would book (Example Group survey, fielded March 10 to 25, 2026).",
        "The fee was raised on May 20, 2026 for all members.",
    ):
        assert fresh.check_event_dates(post(text + SOURCES, date_="2026-05-24"), TODAY) == [], text
    assert rules_of(fresh.check_event_dates(post("The fair opens May 25, 2026." + SOURCES, date_="2026-05-24"), TODAY))


def test_an_ai_phrase_in_the_anchor_text_of_an_external_link_is_a_cited_title():
    cited = "- [The ultimate guide to padel in Marbella](https://club.example/guide) (Example Club)"
    assert "ai_phrase" not in rules_of(generic(cited))
    assert "ai_phrase" in rules_of(generic("Read our ultimate guide to padel in Marbella."))


def test_a_passive_independent_verification_of_a_third_party_is_not_a_first_hand_claim():
    third_party = "A accredited hospital has been independently verified to meet the standard." + SOURCES
    assert "unsupported_first_hand_claim" not in rules_of(run(post(third_party)))
    assert "unsupported_first_hand_claim" in rules_of(run(post("We independently verified every price." + SOURCES)))


def test_an_evidence_heading_may_carry_words_before_the_method_name():
    method = " ".join(["Each provider got the same five prompts and we logged the answers on a set date."] * 3)
    body = f"We tested four providers.\n\n## The Scorecard: How We Tested Four Providers\n\n{method}\n" + SOURCES
    assert "unsupported_first_hand_claim" not in rules_of(run(post(body)))


def test_rows_that_differ_only_by_their_parenthetical_tag_are_different_items():
    body = "| Total (DIY) | $5,000-$8,000 |\n| Total (full-service relocation) | $7,000-$10,000+ |\n"
    assert rc.run(parse_post_text(FM + body), None, TODAY) == []
