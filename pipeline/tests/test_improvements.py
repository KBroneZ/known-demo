"""Changes made to raise the unassisted publication rate, and the guards that keep the bar where it was."""

import json

from dental_pipeline import brief, cli, draft, topics


def test_a_suggestion_is_logged_and_does_not_block_or_trigger_a_fix(model_says):
    answer = json.dumps(
        {
            "verdict": "CORREGIR",
            "findings": [
                {
                    "type": "ai_tell",
                    "kind": "suggestion",
                    "severity": "warn",
                    "quote": "The opening could be punchier",
                    "why": "style",
                    "fix": "x",
                }
            ],
        }
    )
    r = model_says(answer)
    assert r["verdict"] == "PUBLICAR" and not r.get("needs_person")
    assert r["model"]["findings"] == [] and len(r["model"]["suggestions"]) == 1


def test_a_real_error_still_stops_the_post(model_says):
    answer = json.dumps(
        {
            "verdict": "BLOQUEAR",
            "findings": [
                {
                    "type": "false_medical_claim",
                    "kind": "error",
                    "severity": "block",
                    "quote": "scrub it clean with soap",
                    "why": "w",
                    "fix": "f",
                },
                {"type": "ai_tell", "kind": "suggestion", "severity": "info", "quote": "meh", "why": "w", "fix": "f"},
            ],
        }
    )
    r = model_says(answer)
    assert r["verdict"] == "BLOQUEAR" and len(r["model"]["suggestions"]) == 1


def test_an_error_dressed_as_a_suggestion_with_block_severity_is_not_waved_through(model_says):
    hard = json.dumps(
        {
            "verdict": "CORREGIR",
            "findings": [
                {
                    "type": "false_medical_claim",
                    "kind": "suggestion",
                    "severity": "block",
                    "quote": "scrub it",
                    "why": "w",
                    "fix": "f",
                }
            ],
        }
    )
    assert model_says(hard)["verdict"] == "BLOQUEAR"
    soft = json.dumps(
        {
            "verdict": "CORREGIR",
            "findings": [
                {
                    "type": "fact_vs_ficha",
                    "kind": "suggestion",
                    "severity": "block",
                    "quote": "$129 for everyone",
                    "why": "w",
                    "fix": "f",
                }
            ],
        }
    )
    r = model_says(soft)  # a soft-type block is a fixable CORREGIR in the pipeline (existing policy), never a pass
    assert r["verdict"] == "CORREGIR" and len(r["model"]["findings"]) == 1


def test_an_unsourced_claim_without_a_kind_is_still_an_error(model_says):
    answer = json.dumps(
        {
            "verdict": "CORREGIR",
            "findings": [
                {"type": "unsourced_claim", "severity": "warn", "quote": "most patients", "why": "w", "fix": "f"}
            ],
        }
    )
    r = model_says(answer)
    assert r["verdict"] == "CORREGIR" and len(r["model"]["findings"]) == 1


def test_brief_carries_the_clinics_own_service_text_with_its_conditions(site_b):
    c = topics.Candidate(
        "Who can book?", "Family checkups and cleanings", "family-checkups", "checkup", "seed", "seed", 0, 0, "n/a"
    )
    b = brief.build_brief(site_b, c)
    text = " ".join(b["service_text"])
    assert "paying without insurance" in text and "Often, yes" in text
    md = brief.render_markdown(b)
    assert "What the clinic itself says about this service" in md and "Often, yes" in md


def test_writer_rules_forbid_loose_generalities_and_unsupported_clinic_claims():
    assert "No loose generalities" in draft.WRITER_RULES and "only from the lines under" in draft.WRITER_RULES


def test_fix_prompt_points_at_the_paragraph_and_carries_the_models_exact_words():
    current = (
        "---\ntitle: x\n---\n\nFirst paragraph is fine.\n\n"
        "Most patients feel nothing at all during a filling, which is why people relax.\n\nLast one."
    )
    finding = {
        "rule": "model:unsourced_claim",
        "severity": "warn",
        "line": 0,
        "evidence": "Most patients feel nothing at all during a filling",
        "message": "No source for how patients feel. Suggested: say your dentist will explain numbing.",
    }
    prompt = draft.fix_prompt(
        {
            "questions": [],
            "related_questions": [],
            "topic": {
                "question": "q",
                "source": "s",
                "source_id": "i",
                "comments": 0,
                "retrieved": "n/a",
                "intent": "",
                "patient_wording": "",
            },
            "clinic_name": "c",
            "clinic_id": "c",
            "service": "s",
            "service_slug": None,
            "primary_keyword": "k",
            "keyword_note": "n",
            "intent": "i",
            "author": "a",
            "reviewer": "r",
            "word_range": "w",
            "facts": "f",
            "service_summary": "",
            "service_text": [],
            "internal_links": [],
            "sources": [],
        },
        current,
        [finding],
    )
    assert (
        "In this paragraph: 'Most patients feel nothing" in prompt
        and "Suggested: say your dentist will explain numbing" in prompt
    )
    assert "First paragraph is fine" not in prompt.split("Problems:")[1].split("Current post:")[0]


def test_where_paragraph_returns_empty_when_the_text_is_not_found():
    assert draft.where_paragraph("some text", "not in there at all") == ""
    assert draft.where_paragraph("some text", "ab") == ""


def test_a_topic_can_be_picked_by_its_exact_question(site_a, tmp_path, monkeypatch):
    monkeypatch.setattr(topics, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(topics, "cached_titles", lambda *a, **k: ([], "n/a"))
    fresh = type(site_a)(
        site_a.id, site_a.root, site_a.clinic, {}
    )  # a site with no posts yet, whatever is published now
    picked = cli.pick_for(fresh, 1, ["Does getting a tooth-colored filling hurt?", "Do clear aligners hurt?"], False)
    assert [c.question for c in picked] == ["Does getting a tooth-colored filling hurt?", "Do clear aligners hurt?"]
    assert [c.service for c in picked] == ["Tooth-colored fillings", "Clear aligners"]
