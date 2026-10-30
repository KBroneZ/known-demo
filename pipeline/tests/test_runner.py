import json
import shutil
from datetime import date
from pathlib import Path

import pytest
from sample import GOOD, cand, make_call, verdicts

from dental_pipeline import claude, runner


@pytest.fixture
def env_with_calls(site_a, tmp_path, monkeypatch):
    """A site whose posts dir is a temp folder, so publishing cannot touch the real website."""
    (tmp_path / "web" / "src" / "content" / "posts").mkdir(parents=True)
    shutil.copy(site_a.root / "clinic.yaml", tmp_path / "web" / "clinic.yaml")  # a private copy
    fake_site = type(site_a)(site_a.id, tmp_path / "web", site_a.clinic, dict(site_a.posts))
    calls = []

    def fake_claude(stage, prompt, model, system, **kw):
        calls.append(stage)
        return make_call(GOOD, stage=stage)

    monkeypatch.setattr(runner.claude, "call", fake_claude)
    return fake_site, tmp_path, calls


def run_counting_calls(env_with_calls, monkeypatch, seq, **cfg):
    site, tmp, calls = env_with_calls
    monkeypatch.setattr(runner.review, "review", verdicts(*seq))
    config = runner.Config(today=date(2026, 10, 30), use_model_qa=False, **cfg)
    return runner.run_post(cand(), site, config, tmp / "out"), site, tmp, calls


def test_publishar_first_time_publishes(env_with_calls, monkeypatch):
    res, site, tmp, calls = run_counting_calls(env_with_calls, monkeypatch, ["PUBLICAR"])
    assert res["status"] == "published" and res["rounds"] == 0 and calls == ["draft"]
    assert not Path(res["published_to"]).is_absolute() and res["published_to"].endswith(f"{res['slug']}.md")
    published = site.posts_dir / f"{res['slug']}.md"
    assert published.exists() and "fictional practice created for a software demonstration" in published.read_text(
        encoding="utf-8"
    )
    post_dir = tmp / "out" / res["dir"]
    for name in (
        "brief.md",
        "brief.json",
        "draft.md",
        "qa-r0.json",
        "changes.diff",
        "final.md",
        "pr.md",
        "metrics.json",
    ):
        assert (post_dir / name).exists(), name
    assert (post_dir / "changes.diff").read_text(encoding="utf-8") == ""


def test_corregir_then_fixed_runs_one_round(env_with_calls, monkeypatch):
    res, _site, _tmp, calls = run_counting_calls(env_with_calls, monkeypatch, ["CORREGIR", "PUBLICAR"])
    assert res["status"] == "published" and res["rounds"] == 1 and calls == ["draft", "fix-r1"]
    assert res["verdict_path"] == ["CORREGIR", "PUBLICAR"]
    assert any("changes.diff" in item for item in res["human_review"])


def test_bloquear_stops_without_fixing_or_publishing(env_with_calls, monkeypatch):
    res, site, tmp, calls = run_counting_calls(env_with_calls, monkeypatch, ["BLOQUEAR"])
    assert res["status"] == "needs-human" and calls == ["draft"] and res["rounds"] == 0
    assert list(site.posts_dir.glob("*.md")) == []
    assert (tmp / "out" / res["dir"] / "needs-human.md").exists()
    assert any("BLOQUEAR" in item for item in res["human_review"])


def test_round_cap_is_two(env_with_calls, monkeypatch):
    res, site, _tmp, calls = run_counting_calls(env_with_calls, monkeypatch, ["CORREGIR", "CORREGIR", "CORREGIR"])
    assert calls == ["draft", "fix-r1", "fix-r2"] and res["rounds"] == 2
    assert res["status"] == "needs-human" and list(site.posts_dir.glob("*.md")) == []


def test_a_fix_that_introduces_a_block_stops(env_with_calls, monkeypatch):
    res, *_ = run_counting_calls(env_with_calls, monkeypatch, ["CORREGIR", "BLOQUEAR"])
    assert res["verdict_path"] == ["CORREGIR", "BLOQUEAR"] and res["status"] == "needs-human" and res["rounds"] == 1


def test_never_overwrites_an_existing_post(env_with_calls, monkeypatch):
    first, site, tmp, _ = run_counting_calls(env_with_calls, monkeypatch, ["PUBLICAR"])
    slug = first["slug"]
    site.posts_dir.joinpath(f"{slug}.md").write_text("original", encoding="utf-8")
    monkeypatch.setattr(runner.review, "review", verdicts("PUBLICAR"))
    again = runner.run_post(cand(), site, runner.Config(today=date(2026, 10, 30), use_model_qa=False), tmp / "out2")
    assert again["slug"] == f"{slug}-2"  # unique_slug sees the file on disk
    assert site.posts_dir.joinpath(f"{slug}.md").read_text(encoding="utf-8") == "original"


def test_no_publish_flag_keeps_the_site_untouched(env_with_calls, monkeypatch):
    res, site, *_ = run_counting_calls(env_with_calls, monkeypatch, ["PUBLICAR"], publish=False)
    assert res["status"] == "passed-not-published" and list(site.posts_dir.glob("*.md")) == []
    assert res["status"] in runner.STATUS_DONE and "published_to" not in res


def test_dry_run_makes_no_model_calls(env_with_calls):
    site, tmp, calls = env_with_calls
    res = runner.run_post(cand(), site, runner.Config(dry_run=True), tmp / "out")
    assert res["status"] == "dry-run" and calls == [] and (tmp / "out" / res["dir"] / "brief.md").exists()


def test_invalid_draft_gets_one_format_retry_then_fails(env_with_calls, monkeypatch):
    site, tmp, calls = env_with_calls

    def bad_claude(stage, prompt, model, system, **kw):
        calls.append(stage)
        return make_call('---\ntitle: "Short"\ndescription: "tiny"\n---\nnot enough words', stage=stage)

    monkeypatch.setattr(runner.claude, "call", bad_claude)
    res = runner.run_post(cand(), site, runner.Config(use_model_qa=False), tmp / "out")
    assert calls == ["draft", "draft-format-retry"] and res["status"] == "draft-failed"


def test_claude_failure_is_reported_not_raised(env_with_calls, monkeypatch):
    site, tmp, _calls = env_with_calls

    def boom(*a, **k):
        raise claude.ClaudeError("OAuth session expired")

    monkeypatch.setattr(runner.claude, "call", boom)
    res = runner.run_post(cand(), site, runner.Config(use_model_qa=False), tmp / "out")
    assert res["status"] == "draft-failed" and "OAuth" in res["error"] and res["cost_usd"] == 0


def test_metrics_add_up(env_with_calls, monkeypatch):
    res, *_ = run_counting_calls(env_with_calls, monkeypatch, ["CORREGIR", "PUBLICAR"])
    assert res["cost_usd"] == round(sum(c["cost_usd"] for c in res["calls"]), 4) == 0.08
    assert res["input_tokens"] == 2000 and res["output_tokens"] == 1600
    assert set(res["stage_seconds"]) >= {"brief", "draft", "qa", "fix-r1"}


def test_claude_wrapper_parses_cost_and_flags_errors():
    text, cost, usage = claude.parse_output(
        json.dumps({"result": "hi", "total_cost_usd": 0.0123, "usage": {"input_tokens": 5}})
    )
    assert (text, cost, usage["input_tokens"]) == ("hi", 0.0123, 5)
    with pytest.raises(claude.ClaudeError):
        claude.parse_output(json.dumps({"is_error": True, "result": "OAuth session expired"}))
    with pytest.raises(claude.ClaudeError):
        claude.parse_output("not json")
    cmd = claude.build_command("claude", "sonnet", "sys", 0.5)
    assert "--tools" in cmd and cmd[cmd.index("--tools") + 1] == "" and "--setting-sources" in cmd


def test_approve_publishes_a_corregir_leftover_and_records_who(env_with_calls, monkeypatch):
    res, site, tmp, _ = run_counting_calls(env_with_calls, monkeypatch, ["CORREGIR", "CORREGIR", "CORREGIR"])
    post_dir = tmp / "out" / res["dir"]
    with pytest.raises(runner.ApprovalError, match="--by"):
        runner.approve(post_dir, site, " ")
    out = runner.approve(post_dir, site, "Andrew", "only model nitpicks left")
    assert (
        out["status"] == "published" and out["approval"]["by"] == "Andrew" and out["approval"]["overrode"] == "CORREGIR"
    )
    assert (site.posts_dir / f"{res['slug']}.md").exists()
    with pytest.raises(runner.ApprovalError):  # twice is refused
        runner.approve(post_dir, site, "Andrew")


def test_approve_refuses_bloquear(env_with_calls, monkeypatch):
    res, site, tmp, _ = run_counting_calls(env_with_calls, monkeypatch, ["BLOQUEAR"])
    with pytest.raises(runner.ApprovalError, match="BLOQUEAR"):
        runner.approve(tmp / "out" / res["dir"], site, "Andrew")
    assert list(site.posts_dir.glob("*.md")) == []
