import pytest
from conftest import rules_of

from qa_gate import rules_content as rc


@pytest.mark.parametrize(
    "text",
    [
        "As an AI language model, I cannot give advice.",
        "I hope this helps!",
        "Let me know if you'd like me to adjust the tone.",
        "Certainly! Here is the revised version of your post.",
    ],
)
def test_chatbot_residue_blocks(make_post, clinic, text):
    assert "chatbot_residue" in rules_of(rc.check_chatbot(make_post(text), clinic))


def test_placeholders_block(make_post, clinic):
    assert "placeholder" in rules_of(rc.check_chatbot(make_post("Call [insert phone] today. TODO fix"), clinic))


def test_clean_text_has_no_chatbot_findings(make_post, clinic):
    assert rc.check_chatbot(make_post("Our team will let you know what to expect at the visit."), clinic) == []


def test_ai_phrases_warn(make_post, clinic):
    findings = rc.check_ai_phrases(make_post("In today's fast-paced world, let's delve into your smile."), clinic)
    assert {f.rule for f in findings} == {"ai_phrase"}
    assert all(f.severity == "warn" for f in findings)
    assert len(findings) >= 2


def test_plain_text_has_no_ai_phrases(make_post, clinic):
    assert (
        rc.check_ai_phrases(make_post("Brush twice a day and floss once. Book a visit every six months."), clinic) == []
    )


@pytest.mark.parametrize(
    "text",
    [
        "We guarantee perfect results.",
        "Your implant is guaranteed to last.",
        "100% success rate for implants.",
        "A permanent solution for every patient.",
        "Implants that last a lifetime.",
        "We promise a visibly brighter smile.",
        "Our team will assure you perfect results.",
    ],
)
def test_prohibited_promises_block(make_post, clinic, text):
    assert "prohibited_promise" in rules_of(rc.check_promises(make_post(text), clinic))


@pytest.mark.parametrize(
    "text",
    [
        "No dentist can guarantee how long a crown will last.",
        "We do not guarantee any particular result.",
        "Results vary and are never certain.",
    ],
)
def test_negated_promises_pass(make_post, clinic, text):
    assert rc.check_promises(make_post(text), clinic) == []


def test_plain_promise_to_help_passes(make_post, clinic):
    assert rc.check_promises(make_post("We promise to answer your questions at every step."), clinic) == []
    assert rc.check_testimonials(make_post("A patient with diabetes should tell the dentist."), clinic) == []


def test_superlatives(make_post, clinic):
    assert rules_of(rc.check_superlatives(make_post("We are the best dentist in Austin."), clinic)) == [
        "unsupported_superlative"
    ]
    assert rules_of(rc.check_superlatives(make_post("Austin's top-rated dental practice."), clinic)) == [
        "unsupported_superlative"
    ]
    assert rc.check_superlatives(make_post("The best time to see your dentist is before pain starts."), clinic) == []


def test_link_in_paragraph_does_not_excuse_a_superlative(make_post, clinic):
    text = "We are Austin's top-rated dental team ([Poll](https://example.org/poll))."
    assert rules_of(rc.check_superlatives(make_post(text), clinic)) == ["unsupported_superlative"]


@pytest.mark.parametrize(
    "text",
    [
        "Bluebonnet Hollow Dental is Austin's most trusted name for families, honestly second to none.",
        "Our team is the leading choice for implants.",
        "We are unrivaled in gentle care.",
    ],
)
def test_self_referential_superlatives_warn(make_post, clinic, text):
    assert rules_of(rc.check_superlatives(make_post(text), clinic)) == ["unsupported_superlative"]


def test_we_are_without_superlative_passes(make_post, clinic):
    assert (
        rc.check_superlatives(make_post("We are open Monday through Thursday and we are happy to help."), clinic) == []
    )


def test_superlative_allowed_when_award_on_file(make_post, clinic):
    from qa_gate.loader import Clinic

    with_award = Clinic({**clinic.data, "awards": ["Best of Austin 2026"]})
    assert rc.check_superlatives(make_post("We are the best dentist in Austin."), with_award) == []


@pytest.mark.parametrize(
    "text",
    [
        '> "I loved my visit and my teeth have never felt better." — Jessica R., patient',
        "One patient told us she was nervous before her visit.",
        "Check out our 5-star reviews.",
        '"My teeth are brighter and nothing hurt," says Maria T., a recent patient.',
        "A patient who came in last month with a cracked molar told us she felt fine within the hour.",
        'Here is what happened: "I was so nervous but the whole visit felt easy and quick."',
    ],
)
def test_testimonials_block(make_post, clinic, text):
    assert rules_of(rc.check_testimonials(make_post(text), clinic)) == ["fake_testimonial"]


def test_testimonials_allowed_when_on_file(make_post, clinic):
    from qa_gate.loader import Clinic

    with_file = Clinic({**clinic.data, "testimonials_on_file": ["T-001"]})
    assert rc.check_testimonials(make_post("One patient told us she liked it."), with_file) == []


def test_medical_myths_block(make_post, clinic):
    assert rules_of(rc.check_myths(make_post("Fluoride is a poison that you should avoid."), clinic)) == [
        "medical_myth"
    ]
    assert rules_of(rc.check_myths(make_post("Scrub it clean with soap before replanting."), clinic)) == [
        "medical_myth"
    ]
    assert rules_of(
        rc.check_myths(make_post("Placing an aspirin directly against the gum helps numb pain."), clinic)
    ) == ["medical_myth"]
    assert rules_of(rc.check_myths(make_post("Bleeding gums are normal when you start flossing."), clinic)) == [
        "medical_myth"
    ]


def test_myth_pattern_negated_passes(make_post, clinic):
    assert rc.check_myths(make_post("Rinse it gently with water. Do not scrub it."), clinic) == []


def test_unsourced_stats_warn(make_post, clinic):
    for text in (
        "Studies show most adults need a cleaning.",
        "About 93% of patients feel no pain.",
        "9 out of 10 dentists agree.",
        "This is clinically proven to work.",
        "Studies have found that regular visits keep more teeth.",
        "Researchers have shown a link.",
    ):
        assert rules_of(rc.check_unsourced_stats(make_post(text), clinic)) == ["unsourced_stat"], text


def test_stat_with_link_in_paragraph_passes(make_post, clinic):
    text = "About 90% of adults have had a cavity ([NIDCR](https://www.nidcr.nih.gov/health-info/tooth-decay))."
    assert rc.check_unsourced_stats(make_post(text), clinic) == []


def test_stat_link_must_be_in_the_same_paragraph(make_post, clinic):
    text = "See [NIDCR](https://www.nidcr.nih.gov/health-info/tooth-decay).\n\nStudies show it works."
    assert rules_of(rc.check_unsourced_stats(make_post(text), clinic)) == ["unsourced_stat"]


def test_rules_ignore_code_and_jsonld(make_post, clinic):
    body = '```\nGuaranteed 100% success\n```\n<script type="application/ld+json">\n{"x": "guaranteed"}\n</script>\n'
    assert rc.run(make_post(body), clinic) == []


# post-heldout3 additions ----------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Tooth-colored fillings last forever.",
        "Once the canal is sealed, the infection cannot return.",
        "Your crown will never wear out.",
    ],
)
def test_absolute_outcome_promises_block(make_post, clinic, text):
    assert "prohibited_promise" in rules_of(rc.check_promises(make_post(text), clinic))


def test_universal_quantifier_with_duration_is_flagged(make_post, clinic):
    findings = rc.check_unsourced_stats(make_post("Every adult finishes aligner treatment in six weeks."), clinic)
    assert rules_of(findings) == ["unsourced_stat"]
    assert rc.check_unsourced_stats(make_post("Every visit starts with a gum check."), clinic) == []


def test_absolute_clinic_claims_warn(make_post, clinic):
    for text in (
        "Dr. Elena Marsh completes every root canal in a single visit.",
        "We resolve all emergencies on the same day.",
    ):
        assert rules_of(rc.check_clinic_absolutes(make_post(text), clinic)) == ["absolute_clinic_claim"], text
    assert rc.check_clinic_absolutes(make_post("We treat every patient with respect."), clinic) == []


def test_in_one_visit_is_not_a_statistic(make_post, clinic):
    text = "Our family checkups include exams and cleanings for every age in one visit."
    assert rc.check_unsourced_stats(make_post(text), clinic) == []
    assert rules_of(
        rc.check_unsourced_stats(make_post("Every adult finishes aligner treatment in six weeks."), clinic)
    ) == ["unsourced_stat"]
