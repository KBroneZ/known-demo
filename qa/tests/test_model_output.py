"""Review 08 / H2: the model's own verdict and odd severities must never turn into a pass."""

import json

import pytest

from qa_gate import llm


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("BLOQUEAR", "BLOQUEAR"),
        ("block", "BLOQUEAR"),
        ("BLOCK", "BLOQUEAR"),
        (" Bloquear. ", "BLOQUEAR"),
        ("reject", "BLOQUEAR"),
        ("CORREGIR", "CORREGIR"),
        ("fix", "CORREGIR"),
        ("Needs Changes", "CORREGIR"),
        ("PUBLICAR", "PUBLICAR"),
        ("publish", "PUBLICAR"),
        ("OK", "PUBLICAR"),
        ("maybe?", None),
        ("", None),
        (None, None),
        (3, None),
    ],
)
def test_verdict_synonyms(raw, expected):
    assert llm.normalize_verdict(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("block", "block"),
        ("BLOCK", "block"),
        ("Blocker", "block"),
        ("critical", "block"),
        ("HIGH", "block"),
        ("warn", "warn"),
        ("Warning", "warn"),
        ("medium", "warn"),
        ("info", "info"),
        ("INFO", "info"),
        ("low", "info"),
        ("catastrophic", "block"),
        ("", "block"),
        (None, "block"),
        (7, "block"),  # unknown is block, never dropped
    ],
)
def test_severity_synonyms_and_unknown_is_block(raw, expected):
    assert llm.normalize_severity(raw) == expected


def test_finding_that_is_not_a_dict_is_kept_as_a_block():
    f = llm.normalize_finding("the dentist is fake")
    assert f["severity"] == "block" and f["quote"] == "the dentist is fake"


@pytest.fixture
def run(monkeypatch, tmp_path):
    def _run(model_answer):
        monkeypatch.setattr(llm.shutil, "which", lambda name: "claude")
        payload = json.dumps({"result": model_answer, "total_cost_usd": 0.01})
        monkeypatch.setattr(llm, "_run", lambda *a, **k: (0, payload, ""))
        return llm.run_backend("claude", "prompt", tmp_path / "p.md", tmp_path / "o.txt")

    return _run


def test_capitalised_block_severity_blocks(run):
    out = run(
        '{"verdict": "BLOQUEAR", "findings": [{"type": "false_medical_claim", "severity": "BLOCK", "quote": "scrub '
        'it"}]}'
    )
    assert out["verdict"] == "BLOQUEAR" and out["findings"][0]["severity"] == "block"


def test_empty_findings_with_a_blocking_verdict_still_blocks(run):
    assert run('{"verdict": "BLOQUEAR", "findings": []}')["verdict"] == "BLOQUEAR"


def test_unknown_verdict_needs_a_person_even_with_no_findings(run):
    out = run('{"verdict": "looks fine to me", "findings": []}')
    assert out["verdict"] == "CORREGIR" and "needs a person" in out["verdict_note"]
    out = run('{"findings": []}')
    assert out["verdict"] == "CORREGIR"


def test_model_contradicting_itself_takes_the_worse(run):
    out = run('{"verdict": "PUBLICAR", "findings": [{"type": "x", "severity": "critical", "quote": "q"}]}')
    assert out["verdict"] == "BLOQUEAR"


def test_uninterpretable_answer_is_not_ok(run):
    assert run("I think the post is great!")["status"] == "unparsed"
    assert run('{"error": "rate limited"}')["status"] == "unparsed"


def test_clean_answer_passes(run):
    out = run('{"verdict": "PUBLICAR", "findings": [{"type": "x", "severity": "info", "quote": "q"}]}')
    assert out["status"] == "ok" and out["verdict"] == "PUBLICAR"


# error vs suggestion --------------------------------------------------------------------------------------------


def test_a_suggestion_is_logged_and_never_blocks(run):
    out = run(
        '{"verdict": "PUBLICAR", "findings": [{"type": "ai_tell", "kind": "suggestion", "severity": "warn", "quote": '
        '"q"}]}'
    )
    f = out["findings"][0]
    assert out["verdict"] == "PUBLICAR" and f["kind"] == "suggestion" and f["severity"] == "info"


def test_corregir_resting_only_on_suggestions_does_not_stand(run):
    out = run(
        '{"verdict": "CORREGIR", "findings": [{"type": "other", "kind": "style", "severity": "warn", "quote": "q"}]}'
    )
    assert out["verdict"] == "PUBLICAR"


def test_missing_or_unknown_kind_is_an_error(run):
    for kind in ('', ', "kind": "maybe"', ', "kind": null'):
        answer = (
            '{"verdict": "CORREGIR", "findings": [{"type": "unsourced_claim", "severity": "warn", "quote": "q"'
            + kind
            + "}]}"
        )
        out = run(answer)
        assert out["findings"][0]["kind"] == "error" and out["verdict"] == "CORREGIR", kind


def test_a_suggestion_that_claims_severity_block_is_an_error(run):
    out = run(
        '{"verdict": "CORREGIR", "findings": [{"type": "x", "kind": "suggestion", "severity": "block", "quote": "q"}]}'
    )
    assert out["findings"][0]["kind"] == "error" and out["verdict"] == "BLOQUEAR"


def test_blocking_verdict_is_not_softened_by_suggestion_only_findings(run):
    out = run(
        '{"verdict": "BLOQUEAR", "findings": [{"type": "x", "kind": "suggestion", "severity": "info", "quote": "q"}]}'
    )
    assert out["verdict"] == "BLOQUEAR"


def test_the_prompt_defines_both_kinds_and_fails_closed():
    from qa_gate.llm import PROMPT_TEMPLATE

    assert "kind \"error\"" in PROMPT_TEMPLATE and "kind \"suggestion\"" in PROMPT_TEMPLATE
    assert "If you are unsure which kind, choose error" in PROMPT_TEMPLATE
