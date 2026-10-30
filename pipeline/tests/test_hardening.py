"""Review 08: the pipeline must fail closed. Every case here is a way a bad post could have reached the site, or a run
could have lost work."""

import json
from datetime import date

import pytest
from sample import GOOD, cand, make_call, run, verdicts

from dental_pipeline import brief, claude, clinicdata, draft, intent, review, runner, sitefiles, topics
from dental_pipeline.clinicdata import QA_ROOT
from qa_gate import links, llm

# H2: the model's own answer ----------------------------------------------------------------------------------


def test_capitalised_block_on_a_hard_type_blocks(model_says):
    r = model_says(
        '{"verdict": "BLOQUEAR", "findings": '
        '[{"type": "false_medical_claim", "severity": "BLOCK", "quote": "scrub it"}]}'
    )
    assert r["verdict"] == "BLOQUEAR" and r["model"]["findings"][0]["severity"] == "block"


@pytest.mark.parametrize("severity", ["critical", "HIGH", "Blocker", "catastrophic", "", None])
def test_block_synonyms_and_unknown_severity_block_a_hard_type(model_says, severity):
    answer = json.dumps(
        {"verdict": "BLOQUEAR", "findings": [{"type": "chatbot_residue", "severity": severity, "quote": "As an AI"}]}
    )
    assert model_says(answer)["verdict"] == "BLOQUEAR"


def test_unknown_severity_on_a_soft_type_is_kept_not_dropped(model_says):
    r = model_says(
        '{"verdict": "CORREGIR", "findings": '
        '[{"type": "unsourced_claim", "severity": "wobbly", "quote": "most people"}]}'
    )
    assert r["verdict"] == "CORREGIR" and len(r["model"]["findings"]) == 1


def test_blocking_verdict_with_no_findings_stops_for_a_person(model_says):
    r = model_says('{"verdict": "BLOQUEAR", "findings": []}')
    assert r["verdict"] == "BLOQUEAR" and r["needs_person"] and "no actionable finding" in r["needs_person_reason"]


def test_blocking_verdict_with_only_info_findings_stops_for_a_person(model_says):
    r = model_says('{"verdict": "BLOQUEAR", "findings": [{"type": "other", "severity": "info", "quote": "x"}]}')
    assert r["verdict"] == "BLOQUEAR" and r["needs_person"]


def test_unreadable_verdict_is_never_a_pass(model_says):
    for answer in (
        '{"verdict": "looks great", "findings": []}',
        '{"findings": []}',
        '{"verdict": null, "findings": []}',
    ):
        r = model_says(answer)
        assert r["verdict"] != "PUBLICAR" and r["needs_person"], answer


def test_model_answer_that_is_not_json_is_never_a_pass(model_says):
    for answer in ("The post is great, publish it!", '{"error": "rate limited"}', "{broken json"):
        r = model_says(answer)
        assert r["verdict"] == "CORREGIR" and r["needs_person"] and r["model"]["status"] == "unparsed", answer


def test_model_failure_is_never_a_pass(monkeypatch, site_a, tmp_path):
    monkeypatch.setattr(llm.shutil, "which", lambda name: None)
    text = draft.assemble(draft.parse_answer(GOOD), brief.build_brief(site_a, cand()), "x-slug", date.today())
    r = review.review(
        text,
        site_a,
        tmp_path,
        "r0",
        "haiku",
        use_model=True,
        offline=True,
        link_cache=links.load_cache(QA_ROOT / "fixtures" / "link-cache.json"),
    )
    assert r["verdict"] == "CORREGIR" and r["needs_person"]


def test_a_clean_answer_still_passes(model_says):
    r = model_says('{"verdict": "PUBLICAR", "findings": [{"type": "other", "severity": "info", "quote": "x"}]}')
    assert r["verdict"] == "PUBLICAR" and not r.get("needs_person")


def test_only_pool_url_noise_does_not_stop_a_post(model_says):
    url = "https://www.mouthhealthy.org/all-topics-a-z/bridges"
    answer = json.dumps(
        {
            "verdict": "CORREGIR",
            "findings": [{"type": "broken_or_fake_source", "severity": "warn", "quote": f"[x]({url})"}],
        }
    )
    r = model_says(answer)
    assert r["verdict"] == "PUBLICAR" and r["model"]["dropped_unverifiable_url"] == 1 and not r.get("needs_person")


def test_contradicting_itself_takes_the_worse(model_says):
    r = model_says(
        '{"verdict": "PUBLICAR", "findings": '
        '[{"type": "prohibited_promise", "severity": "BLOCK", "quote": "guarantee"}]}'
    )
    assert r["verdict"] == "BLOQUEAR"


def test_needs_person_skips_the_fix_rounds(env, monkeypatch):
    site, tmp = env
    calls = []
    monkeypatch.setattr(
        runner.claude,
        "call",
        lambda stage, prompt, model, system, **kw: calls.append(stage) or make_call(GOOD, stage=stage),
    )

    def unreadable(post_file, site, work_dir, name, qa_model, use_model=True, offline=False, link_cache=None):
        return {
            "name": name,
            "rules_verdict": "PUBLICAR",
            "rules_findings": [],
            "verdict": "CORREGIR",
            "needs_person": True,
            "needs_person_reason": "model review unavailable (unparsed); needs a person",
            "model": {"status": "unparsed"},
        }

    monkeypatch.setattr(runner.review, "review", unreadable)
    res = runner.run_post(cand(), site, runner.Config(today=date(2026, 10, 30), use_model_qa=True), tmp / "out")
    assert calls == ["draft"] and res["status"] == "needs-human" and res["rounds"] == 0
    assert any("could not give a usable answer" in i for i in res["human_review"])
    assert list(site.posts_dir.glob("*.md")) == []


# M4 / M5 ------------------------------------------------------------------------------------------------------


def test_no_publish_is_not_reported_as_published(env, monkeypatch):
    monkeypatch.setattr(runner.review, "review", verdicts("PUBLICAR"))
    s, t = env
    res = runner.run_post(
        cand(), s, runner.Config(today=date(2026, 10, 30), use_model_qa=False, publish=False), t / "out-np"
    )
    assert res["status"] == "passed-not-published" and "published_to" not in res
    pr = (t / "out-np" / res["dir"] / "pr.md").read_text(encoding="utf-8")
    assert "NOT copied" in pr and "(copied to the website)" not in pr
    assert any("NOT copied" in i for i in res["human_review"])


def test_qa_crash_does_not_abort_the_run_or_lose_run_json(env, monkeypatch):
    site, tmp = env
    monkeypatch.setattr(runner.claude, "call", lambda stage, prompt, model, system, **kw: make_call(GOOD, stage=stage))
    calls = {"n": 0}

    def sometimes_crashes(post_file, site, work_dir, name, qa_model, use_model=True, offline=False, link_cache=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise KeyError("slug")
        return {
            "name": name,
            "rules_verdict": "PUBLICAR",
            "rules_findings": [],
            "model": {"status": "skipped"},
            "verdict": "PUBLICAR",
        }

    monkeypatch.setattr(runner.review, "review", sometimes_crashes)
    cfg = runner.Config(today=date(2026, 10, 30), use_model_qa=False)
    summary = runner.run_all([(site, cand()), (site, cand())], cfg, tmp / "out", "crashy")
    first, second = summary["posts"]
    assert first["status"] == "qa-crashed" and first["verdict_path"] == ["BLOQUEAR"] and "KeyError" in first["error"]
    assert second["status"] == "published"
    assert (tmp / "out" / "crashy" / "run.json").exists() and "qa-crashed" in (
        tmp / "out" / "crashy" / "RUN.md"
    ).read_text(encoding="utf-8")


def test_a_crash_outside_qa_is_recorded_and_the_next_topic_runs(env, monkeypatch):
    site, tmp = env
    monkeypatch.setattr(runner.claude, "call", lambda stage, prompt, model, system, **kw: make_call(GOOD, stage=stage))
    monkeypatch.setattr(runner.review, "review", verdicts("PUBLICAR", "PUBLICAR"))
    real = runner.brief_mod.build_brief
    seen = {"n": 0}

    def flaky(site, cand):
        seen["n"] += 1
        if seen["n"] == 1:
            raise RuntimeError("disk on fire")
        return real(site, cand)

    monkeypatch.setattr(runner.brief_mod, "build_brief", flaky)
    summary = runner.run_all(
        [(site, cand()), (site, cand())], runner.Config(today=date(2026, 10, 30), use_model_qa=False), tmp / "out", "r"
    )
    assert [p["status"] for p in summary["posts"]] == ["crashed", "published"]
    assert (tmp / "out" / "r" / "run.json").exists()


def test_final_text_must_pass_the_rules_too(env, monkeypatch):
    site, tmp = env
    monkeypatch.setattr(runner.claude, "call", lambda stage, prompt, model, system, **kw: make_call(GOOD, stage=stage))
    seq = iter(["PUBLICAR", "CORREGIR"])  # the draft passes; the footer-included text does not

    def fake(post_file, site, work_dir, name, qa_model, use_model=True, offline=False, link_cache=None):
        v = next(seq)
        bad = (
            [{"rule": "raw_html", "severity": "block", "line": 3, "evidence": "<b>", "message": "m"}]
            if v != "PUBLICAR"
            else []
        )
        return {"name": name, "rules_verdict": v, "rules_findings": bad, "model": {"status": "skipped"}, "verdict": v}

    monkeypatch.setattr(runner.review, "review", fake)
    res = runner.run_post(cand(), site, runner.Config(today=date(2026, 10, 30), use_model_qa=False), tmp / "out")
    assert res["status"] == "needs-human" and "does not pass the rules" in res["error"]
    assert list(site.posts_dir.glob("*.md")) == []


def test_failed_model_call_cost_is_still_counted(env, monkeypatch):
    site, tmp = env

    def boom(*a, **k):
        raise claude.ClaudeError("claude reported an error: overloaded", 0.0123)

    monkeypatch.setattr(runner.claude, "call", boom)
    res = runner.run_post(cand(), site, runner.Config(use_model_qa=False), tmp / "out")
    assert res["status"] == "draft-failed" and res["cost_usd"] == 0.0123
    assert res["calls"][0]["stage"].endswith("(failed)")


def test_claude_error_carries_the_cost():
    with pytest.raises(claude.ClaudeError) as err:
        claude.parse_output(json.dumps({"is_error": True, "result": "overloaded", "total_cost_usd": 0.02}))
    assert err.value.cost_usd == 0.02


# M9 -----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("title", ["!!!!!!!!!!!!!!", "Is a an the of to", "ºª ¿¿ ¡¡", "........ ----"])
def test_a_title_with_no_usable_words_is_an_error_not_dot_md(title):
    with pytest.raises(draft.DraftError, match="empty slug"):
        draft.unique_slug(title, set())


def test_empty_slug_draft_fails_and_writes_nothing(env, monkeypatch):
    site, tmp = env
    weird = GOOD.replace("Is Professional Teeth Whitening Safe for Sensitive Teeth?", "?????????????")
    monkeypatch.setattr(runner.claude, "call", lambda stage, prompt, model, system, **kw: make_call(weird, stage=stage))
    res = runner.run_post(cand(), site, runner.Config(use_model_qa=False), tmp / "out")
    assert res["status"] == "draft-failed" and "empty slug" in res["error"]
    assert list(site.posts_dir.glob("*")) == []


def test_publish_refuses_a_bad_slug(env):
    site, _tmp = env
    for bad in ("", ".md", "../x", "Has Space", "UPPER"):
        with pytest.raises(sitefiles.PagesEditError, match="refusing"):
            runner.publish(site, bad, "text")
    assert list(site.posts_dir.glob("*")) == []


# M10 ----------------------------------------------------------------------------------------------------------


def test_unindented_pages_list_is_edited(tmp_path):
    path = tmp_path / "clinic.yaml"
    path.write_text("name: X\npages:\n- /\n- /blog\n- /blog/a\nother: 1\n", encoding="utf-8")
    assert sitefiles.add_page_route(path, "/blog/b") is True
    assert path.read_text(encoding="utf-8") == "name: X\npages:\n- /\n- /blog\n- /blog/a\n- /blog/b\nother: 1\n"
    assert miniyaml_pages(path) == ["/", "/blog", "/blog/a", "/blog/b"]


def miniyaml_pages(path):
    from qa_gate import miniyaml

    return miniyaml.loads(path.read_text(encoding="utf-8"))["pages"]


@pytest.mark.parametrize("text", ["pages: [/, /blog]\n", "pages:\nname: X\n", "pages: ~\n", "pages:\n\n"])
def test_pages_in_a_form_it_cannot_edit_fails_loudly(tmp_path, text):
    path = tmp_path / "clinic.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(sitefiles.PagesEditError):
        sitefiles.add_page_route(path, "/blog/z")
    assert path.read_text(encoding="utf-8") == text  # untouched


def test_unparseable_pages_stops_publishing_and_removes_the_post(env, monkeypatch):
    site, tmp = env
    (tmp / "web" / "clinic.yaml").write_text("name: X\npages: [/, /blog]\n", encoding="utf-8")
    res, site, _ = run(env, monkeypatch, ["PUBLICAR"])
    assert res["status"] == "needs-human" and "nothing was published" in res["error"]
    assert list(site.posts_dir.glob("*.md")) == []


def test_write_is_atomic_no_temp_file_left_and_original_survives_a_failed_check(tmp_path, monkeypatch):
    path = tmp_path / "clinic.yaml"
    original = "name: X\npages:\n  - /\n  - /blog\n"
    path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(
        sitefiles, "verify_only_pages_changed", lambda *a: (_ for _ in ()).throw(sitefiles.PagesEditError("no"))
    )
    with pytest.raises(sitefiles.PagesEditError):
        sitefiles.add_page_route(path, "/blog/z")
    assert path.read_text(encoding="utf-8") == original and not list(tmp_path.glob(".*.tmp"))
    monkeypatch.undo()
    sitefiles.add_page_route(path, "/blog/z")
    assert not list(tmp_path.glob(".*.tmp")) and "/blog/z" in path.read_text(encoding="utf-8")


# L7, L10, M7 ---------------------------------------------------------------------------------------------------


def test_approve_a_post_that_passed_but_could_not_be_published_uses_final_md(env, monkeypatch):
    site, tmp = env
    (tmp / "web" / "clinic.yaml").write_text("name: X\npages: [/, /blog]\n", encoding="utf-8")
    res, site, _ = run(env, monkeypatch, ["PUBLICAR"])
    post_dir = tmp / "out" / res["dir"]
    (post_dir / "needs-human.md").unlink()  # only final.md is left to approve from
    assert (post_dir / "final.md").exists()
    (tmp / "web" / "clinic.yaml").write_text(
        "name: X\npages:\n  - /\n  - /blog\n", encoding="utf-8"
    )  # the person fixed it
    out = runner.approve(post_dir, site, "Andrew")
    assert out["status"] == "published" and (site.posts_dir / f"{res['slug']}.md").exists()


def test_approve_in_a_folder_that_is_not_a_post_is_a_clean_error(env, tmp_path):
    site, _tmp = env
    with pytest.raises(runner.ApprovalError, match=r"metrics\.json"):
        runner.approve(tmp_path / "nowhere", site, "Andrew")


def test_site_ids_cannot_escape_the_sites_folder():
    for bad in ("../../x", "a/b", "", "A B", ".."):
        with pytest.raises(ValueError):
            clinicdata.load_site(bad)


def test_related_titles_are_filtered_like_topics(site_a, tmp_path, monkeypatch):
    monkeypatch.setattr(topics, "CACHE_DIR", tmp_path)
    titles = [
        {"id": "1", "title": "Is a tooth-colored filling safe for adults?", "score": 1, "num_comments": 9},
        {
            "id": "2",
            "title": "Should I worry about my filling after wisdom teeth surgery?",
            "score": 1,
            "num_comments": 8,
        },
        {"id": "3", "title": "Does a filling hurt for my 5 year old?", "score": 1, "num_comments": 7},
        {"id": "4", "title": "How much does a filling cost?", "score": 1, "num_comments": 6},
    ]
    cands = topics.candidates_for(site_a, fetch=lambda url: titles)
    top = next(c for c in cands if c.service == "Tooth-colored fillings")
    assert top.related == ("How much does a filling cost?",)
    service = next(s for s in site_a.data["services"] if s["name"] == "Tooth-colored fillings")
    assert intent.is_general_about("How much does a filling cost?", service)
    assert not intent.is_general_about("My filling hurts", service)
