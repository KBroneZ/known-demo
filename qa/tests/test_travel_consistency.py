"""Travel rule (a): the same entity gets two different prices, distances or dates, or one event two weekdays."""

from datetime import date

import pytest
from conftest import rules_of

from qa_gate import rules_travel_consistency as rc
from qa_gate.loader import parse_post_text

FM = (
    '---\ntitle: "Lisbon in three days"\nslug: lisbon\ndate: 2026-05-01\nupdated: 2026-05-01\nauthor: Nora Vale\n'
    'category: cities\n---\n'
)


def run(body: str):
    return rc.run(parse_post_text(FM + body), None, date(2026, 10, 30))


def test_same_entity_two_prices_is_flagged():
    out = run("The Harbor Line ferry costs $12.\n\nLater: the Harbor Line ferry is $15.\n")
    assert rules_of(out) == ["numeric_inconsistency"]
    assert out[0].severity == "warn" and "$12" in out[0].evidence and "$15" in out[0].evidence


def test_same_price_repeated_is_fine():
    assert run("The Harbor Line ferry costs $12.\n\nThe Harbor Line ferry is $12 again in the table.\n") == []


def test_different_entities_do_not_collide():
    assert run("The Harbor Line ferry costs $12.\n\nThe Castle Funicular costs $15.\n") == []


def test_table_row_is_one_unit():
    body = "| Item | Price |\n|---|---|\n| Harbor Line ferry | $12 |\n| Castle Funicular | $15 |\n"
    assert run(body) == []
    body += "\nThe Harbor Line ferry is $14 at the dock.\n"
    assert rules_of(run(body)) == ["numeric_inconsistency"]


def test_qualifier_separates_prices_for_one_entity():
    body = (
        "A 7-day Rail Pass costs $200.\n\nA 14-day Rail Pass costs $320.\n\nChild fares: the Rail Pass is $100 for a "
        "child, adult $200.\n"
    )
    assert run(body) == []


def test_single_inside_a_range_is_compatible_and_range_vs_range_is_not():
    assert run("Entry to the Royal Gardens is $20-$30.\n\nThe Royal Gardens ticket is $25 online.\n") == []
    out = run("The Royal Gardens ticket is $20-$30.\n\nThe Royal Gardens ticket is $22-$34 in summer weekdays.\n")
    assert out == []  # different qualifier (summer weekdays)
    out = run("The Royal Gardens ticket is $20-$30.\n\nThe Royal Gardens ticket is $22-$34.\n")
    assert rules_of(out) == ["numeric_inconsistency"]


def test_floor_and_cap_semantics():
    assert run("Rooms at the Hotel Aurora start from $90.\n\nThe Hotel Aurora room is $120 in May.\n") == []
    out = run("Rooms at the Hotel Aurora start from $150.\n\nThe Hotel Aurora room is $120 in May.\n")
    assert rules_of(out) == ["numeric_inconsistency"]


def test_approximate_values_tolerate_rounding():
    assert run("The Rail Pass costs about $330.\n\nThe Rail Pass costs $329.\n") == []
    assert rules_of(run("The Rail Pass costs $330.\n\nThe Rail Pass costs $329.\n")) == ["numeric_inconsistency"]


def test_currencies_are_not_compared_with_each_other():
    assert run("The Rail Pass costs ¥50,000.\n\nThe Rail Pass costs about $330.\n") == []


def test_distance_conflict_and_unit_conversion():
    out = run("The Ridge Trail is 3.3 miles.\n\nThe Ridge Trail is 5 miles long.\n")
    assert rules_of(out) == ["numeric_inconsistency"]
    assert run("The Ridge Trail is 3.3 miles.\n\nThe Ridge Trail is 5.3 km long.\n") == []


def test_event_two_weekdays_is_flagged():
    out = run(
        "Gold Cup Day is on Thursday and is the busiest day.\n\nPlan for Friday if Gold Cup Day is your priority.\n"
    )
    assert rules_of(out) == ["weekday_inconsistency"]
    assert "Thursday" in out[0].evidence and "Friday" in out[0].evidence


def test_weekday_ranges_and_other_entities_are_ignored():
    assert run("The Night Market runs Tuesday to Saturday.\n\nThe Night Market is busiest on Friday.\n") == []
    assert run("Museum Day is on Thursday.\n\nFood Fair Day is on Friday.\n") == []


def test_same_event_two_dates():
    out = run("The Lantern Festival is held on June 18.\n\nDon't miss the Lantern Festival on June 20.\n")
    assert rules_of(out) == ["date_inconsistency"]
    assert run("The Lantern Festival opens on June 18.\n\nThe Lantern Festival closes on June 20.\n") == []


def test_numbered_entities_stay_separate():
    assert run("Day 1 starts at the Old Market, costing $20.\n\nDay 2 starts at the Old Market, costing $30.\n") == []
    assert run("Terminal 1 opens June 1.\n\nTerminal 2 opens June 9.\n") == []


def test_weekday_that_contradicts_its_own_date_is_blocked():
    out = run("The race is on Friday, June 18, 2026 at noon.\n")
    assert rules_of(out) == ["weekday_date_mismatch"] and out[0].severity == "block"
    assert run("The race is on Thursday, June 18, 2026 at noon.\n") == []
    assert run("The race is on Thursday 18 June 2026 at noon.\n") == []
    assert rules_of(run("The race is on Friday 18 June 2026 at noon.\n")) == ["weekday_date_mismatch"]


def test_amounts_listed_together_in_one_sentence_are_an_enumeration_not_a_conflict():
    assert run("The Rail Pass is $100 for a child and $200 for an adult.\n") == []


def test_sources_section_and_code_are_not_read():
    body = "## Sources\n\nThe Harbor Line ferry costs $12.\n\nThe Harbor Line ferry costs $15.\n"
    assert run(body) == []


@pytest.mark.parametrize(
    "text",
    [
        "Sentences without any entity cost $12 and then $15.",
        "The ferry costs $12. The ferry costs $15.",  # lowercase 'ferry' is not a named entity
    ],
)
def test_no_named_entity_no_finding(text):
    assert run(text + "\n") == []
