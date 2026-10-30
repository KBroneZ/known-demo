"""Travel profile end to end: the fixture sets, the CLI and the model prompt."""

import json
import sys
from datetime import date
from pathlib import Path

import evaluate
import pytest

from qa_gate import cli, gate, llm
from qa_gate.loader import load_clinic, load_post

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "travel"
TODAY = date(2026, 10, 30)


@pytest.fixture(scope="module")
def site():
    return load_clinic(FIXTURES / "site.yaml")


def test_clean_travel_posts_all_pass_with_the_cached_links(site):
    from qa_gate import links

    cache = links.load_cache(FIXTURES / "link-cache.json")
    for path in sorted((FIXTURES / "posts" / "clean").glob("*.md")):
        report, _, _ = gate.check_file(path, site, offline=True, link_cache=cache, max_age_days=None, today=TODAY)
        assert report["verdict"] == "PUBLICAR", (path.name, report["findings"])


def test_seeded_travel_set_rules_only_numbers_are_stable(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["evaluate.py"])
    assert evaluate.main(["--set", "travel-seeded", "--out", str(tmp_path)]) == 0
    result = json.loads((tmp_path / "eval-travel-seeded.json").read_text(encoding="utf-8"))
    assert result["seeded_total"] == 21 and result["seeded_detected"] == 17
    assert result["missed"] == ["T18", "T19", "T20", "T21"]  # the four that need world knowledge: model layer only
    assert result["false_positive_findings"] == 0 and result["clean_false_positives"] == 0


def test_a_contradiction_counts_as_found_on_either_of_its_two_lines():
    errors = [{"id": "X", "file": "set/a.md", "rules": ["numeric_inconsistency"], "line": 5}]
    report = {
        "findings": [{"rule": "numeric_inconsistency", "severity": "warn", "line": 9, "also": [5], "evidence": "e"}],
        "verdict": "CORREGIR",
    }
    assert evaluate.score(errors, {"set/a.md": report})["recall"] == 1.0


def test_report_dict_has_no_also_key_unless_a_finding_has_two_lines():
    from qa_gate.findings import Finding

    assert "also" not in Finding("r", "warn", 1, "e", "m").to_dict()
    assert Finding("r", "warn", 1, "e", "m", also=(4,)).to_dict()["also"] == [4]


def test_cli_runs_a_travel_site_and_rejects_a_bad_today(tmp_path, capsys):
    base = [
        "--clinic",
        str(FIXTURES / "site.yaml"),
        "--offline",
        "--link-cache",
        str(FIXTURES / "link-cache.json"),
        "--max-cache-age-days",
        "-1",
        "--out",
        str(tmp_path),
    ]
    clean = str(FIXTURES / "posts" / "clean" / "01-lisbon-three-days-walkable-plan.md")
    assert cli.main([clean, *base, "--today", "2026-10-30"]) == 0
    assert cli.main([clean, *base, "--today", "30/10/2026"]) == cli.EXIT_ERROR
    # a year later every price and review in the post is stale: the same post stops being a pass
    assert cli.main([clean, *base, "--today", "2027-10-30"]) == 1


def test_travel_prompt_asks_for_entities_figures_and_seasonality_and_carries_the_date(site):
    post = load_post(FIXTURES / "posts" / "clean" / "03-kyoto-cherry-blossom-season-2027.md")
    prompt = llm.build_prompt(post, site, [], independent=True, today=TODAY)
    assert "Today is 2026-10-30" in prompt
    for needle in (
        "Entities",
        "Figures",
        "Seasonality and logistics",
        "entity_not_found",
        "source_does_not_support_figure",
        'kind "error"',
        "If you are unsure which kind, choose error",
        "<site_rules>",
        "profile: travel",
    ):
        assert needle in prompt, needle
    assert "dental" not in prompt.lower() and "ficha" not in prompt


def test_dental_prompt_is_unchanged_by_the_travel_template():
    from qa_gate.loader import load_clinic as load

    clinic = load(Path(__file__).resolve().parent.parent / "fixtures" / "clinic.yaml")
    post = load_post(next((Path(__file__).resolve().parent.parent / "fixtures" / "posts" / "clean").glob("*.md")))
    prompt = llm.build_prompt(post, clinic, [], independent=True)
    assert "dental clinic blog post" in prompt and "<ficha>" in prompt and "Today is" not in prompt


def test_model_findings_of_the_travel_prompt_use_the_same_normalisation():
    f = llm.normalize_finding({"type": "entity_unverified", "kind": "suggestion", "severity": "warn", "quote": "q"})
    assert f["kind"] == "suggestion" and f["severity"] == "info"
    g = llm.normalize_finding({"type": "entity_not_found", "kind": "error", "severity": "warn", "quote": "q"})
    assert g["kind"] == "error" and g["severity"] == "warn"
