import pytest
from conftest import rules_of

from qa_gate import rules_content as rc
from qa_gate.negation import is_negated


@pytest.mark.parametrize(
    "text",
    [
        "There is no doubt that we guarantee a perfect smile.",
        "Our implants are not cheap, but we guarantee they last.",
        "We never take shortcuts and we guarantee results.",
        "No problem, we guarantee your satisfaction.",
    ],
)
def test_negation_elsewhere_in_the_sentence_does_not_excuse_a_promise(make_post, clinic, text):
    assert "prohibited_promise" in rules_of(rc.check_promises(make_post(text), clinic)), text


@pytest.mark.parametrize(
    "text",
    [
        "No dentist can guarantee how long a crown lasts.",
        "We do not guarantee any particular result.",
        "We can't guarantee results.",
        "Nobody should promise you a flawless smile.",
    ],
)
def test_attached_negation_still_excuses_a_promise(make_post, clinic, text):
    assert rc.check_promises(make_post(text), clinic) == [], text


@pytest.mark.parametrize(
    "text",
    [
        "Do not worry, brushing harder cleans better.",
        "It is no secret: fluoride is a poison.",
        "People never ask, but scrub it clean with soap before putting it back.",
    ],
)
def test_negation_elsewhere_does_not_excuse_a_myth(make_post, clinic, text):
    assert rules_of(rc.check_myths(make_post(text), clinic)) == ["medical_myth"], text


def test_negated_myth_is_excused(make_post, clinic):
    assert rc.check_myths(make_post("Rinse it with water and do not scrub it clean."), clinic) == []


def test_is_negated_respects_clause_boundaries():
    text = "We know prices vary, but we guarantee it."
    assert not is_negated(text, text.index("guarantee"))
    text = "We do not guarantee it."
    assert is_negated(text, text.index("guarantee"))
    assert not is_negated("know guarantee", 5)  # "know" is not "no"
