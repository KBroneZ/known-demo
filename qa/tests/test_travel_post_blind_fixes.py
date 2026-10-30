"""Rule changes made after the travel blind set was scored (documented in README as post-blind, v2).

Each test states the general behaviour, not the blind post that exposed it."""

from datetime import date

from conftest import rules_of
from test_travel_site_rules import post, run, site

from qa_gate import rules_travel_consistency as rc
from qa_gate import rules_travel_fresh as rf
from qa_gate import rules_travel_site as rs
from qa_gate import travel_text as t
from qa_gate.loader import parse_post_text

FM = '---\ntitle: "x"\nslug: a\ndate: 2026-05-01\nupdated: 2026-05-01\nauthor: Nora Vale\ncategory: c\n---\n'


def consistency(body: str):
    return rc.run(parse_post_text(FM + body), None, date(2026, 10, 30))


def test_the_same_entity_with_an_extra_word_in_one_place_is_still_the_same_entity():
    assert rc.same_entity("donau licht", "donau licht boats")
    assert not rc.same_entity("tokyo", "tokyo metro")  # a single word is too weak to merge on
    body = (
        "| Item | Operator | Price |\n|---|---|---|\n| Evening river cruise | Donau Licht Boats | EUR 28 |\n\nThe "
        "Donau Licht evening cruise costs EUR 32 per adult.\n"
    )
    assert rules_of(consistency(body)) == ["numeric_inconsistency"]


def test_opening_hours_words_do_not_split_two_prices():
    body = (
        "The Donau Licht evening cruise costs EUR 28.\n\nBoarding opens early, and the Donau Licht evening cruise "
        "costs EUR 32.\n"
    )
    assert rules_of(consistency(body)) == ["numeric_inconsistency"]


def test_per_adult_is_the_default_price_not_a_different_one():
    body = "The Night Tram ride costs $10.\n\nThe Night Tram ride is $14 per adult.\n"
    assert rules_of(consistency(body)) == ["numeric_inconsistency"]
    body = "The Night Tram ride costs $10 per adult.\n\nThe Night Tram ride is $5 for a child.\n"
    assert consistency(body) == []


def test_two_different_items_at_one_place_are_not_a_conflict():
    body = (
        "| Coffee house tasting plate | Cafe Hinterhof | EUR 14 |\n\nThe walnut torte slice at Cafe Hinterhof costs "
        "EUR 6.80.\n"
    )
    assert consistency(body) == []


def test_review_date_with_trailing_punctuation_and_other_formats_parse():
    assert t.parse_any_date("2026-06-03.") == date(2026, 6, 3)
    assert t.parse_any_date("(checked 2026-06-03)") == date(2026, 6, 3)
    body = "Last reviewed 2026-06-03.\n\n## Sources\n\n- x\n"
    assert "review_stamp_is_publish_date" in rules_of(run(post(body, date_="2026-06-03", updated="2026-06-03")))


def test_more_currencies_count_as_prices():
    assert [q.text for q in t.quantities("A bowl costs VND 60,000 and a ride THB 200 or ₫50,000.")] == [
        "VND 60,000",
        "THB 200",
        "₫50,000",
    ]
    assert t.quantities("The TOP 10 list has 5 items.") == []
    body = "The cooking class costs VND 750,000.\n\n## Sources\n\n- x\n"
    assert rules_of(run(post(body))) == ["price_no_as_of"]


def test_price_without_as_of_points_at_every_line_that_states_a_price():
    body = "The class costs VND 750,000.\n\nA tour is VND 540,000.\n\n## Sources\n\n- x\n"
    f = rf.check_prices_dated(post(body), site(), date(2026, 10, 30))[0]
    assert f.also and len(f.also) == 1


def test_editors_as_the_subject_of_a_first_hand_claim():
    for text in (
        "Our editors rode the cable car three mornings to confirm the queues.",
        "Our team timed every transfer on two separate trips.",
    ):
        assert "unsupported_first_hand_claim" in rules_of(run(post(f"{text}\n\n## Sources\n\n- x\n")))
    assert "unsupported_first_hand_claim" not in rules_of(
        run(post("Our editors have not visited yet.\n\n## Sources\n\n- x\n"))
    )
    assert rs.EXPERIENCE_CLAIMS
