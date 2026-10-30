import json
from pathlib import Path

from vistrack import db
from vistrack.config import load_config
from vistrack.engines.base import Citation, RawResult
from vistrack.engines.cli_common import ProcResult
from vistrack.judge import JudgeVerdict, apply_judge, claude_cli_judge
from vistrack.reextract import reextract
from vistrack.runner import _store_result
from vistrack.validate import evaluate_real

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "config" / "austin_real.yaml"


class FakeEngine:
    key, model, tool_version = "codex_cli", "m", "t"


def seed(tmp_path, answer, urls):
    cfg = load_config(CFG)
    conn = db.connect(tmp_path / "t.db")
    p = type("P", (), {"id": "p01", "text": "q"})()
    res = RawResult(
        answer_text=answer, citations=[Citation(u, None, i, "cited") for i, u in enumerate(urls, 1)], raw={"a": 1}
    )
    _store_result(cfg, conn, FakeEngine(), p, 1, res, "b", False, tmp_path / "raw", None)
    conn.commit()
    return cfg, conn


def test_reextract_applies_new_alias_and_domain_without_new_queries(tmp_path):
    cfg, conn = seed(tmp_path, "Try Practice F & Associates.", ["https://www.practice-f.example/x"])
    # simulate the old config: no alias, no domain match stored
    conn.execute("DELETE FROM mention")
    conn.execute("UPDATE citation SET brand_id = NULL")
    assert reextract(conn, cfg, "b") == 1
    assert conn.execute("SELECT brand_id FROM mention").fetchall()[0]["brand_id"] == "practice-f"
    assert conn.execute("SELECT brand_id FROM citation").fetchone()["brand_id"] == "practice-f"


def test_reextract_keeps_judge_verdicts_and_rereconciles(tmp_path):
    cfg, conn = seed(tmp_path, "Practice E Dentistry is open. The Main Street smile practice is great.", [])
    verdict = JudgeVerdict({"practice-e": 1, "practice-c": 2}, [])
    apply_judge(conn, cfg, "b", lambda t: verdict, "fake", log=lambda m: None)
    reextract(conn, cfg, "b")
    how = {r["brand_id"]: r["matched_by"] for r in conn.execute("SELECT * FROM mention")}
    assert how == {"practice-e": "both", "practice-c": "judge"}
    assert conn.execute("SELECT COUNT(*) FROM judge_verdict").fetchone()[0] == 1


def test_apply_judge_keeps_regex_and_flags_judge_only(tmp_path):
    cfg, conn = seed(tmp_path, "Practice E Dentistry is open. The Main Street smile practice is great.", [])
    verdict = JudgeVerdict({"practice-e": 1, "practice-c": 2}, ["Other Dental"])
    counts = apply_judge(conn, cfg, "b", lambda text: verdict, "fake", log=lambda m: None)
    assert counts == {"judged": 1, "failed": 0}
    how = {r["brand_id"]: r["matched_by"] for r in conn.execute("SELECT * FROM mention")}
    assert how == {"practice-e": "both", "practice-c": "judge"}
    assert conn.execute("SELECT name FROM other_business").fetchone()["name"] == "Other Dental"
    # second call has nothing left to judge
    assert apply_judge(conn, cfg, "b", lambda t: verdict, "fake", log=lambda m: None)["judged"] == 0


def test_apply_judge_survives_a_failing_judge(tmp_path):
    cfg, conn = seed(tmp_path, "Practice E Dentistry.", [])

    def boom(text):
        raise RuntimeError("claude judge failed (quota): usage limit")

    counts = apply_judge(conn, cfg, "b", boom, "fake", log=lambda m: None)
    assert counts["failed"] == 1 and conn.execute("SELECT COUNT(*) FROM mention").fetchone()[0] == 1


def test_claude_cli_judge_command_and_parsing(monkeypatch):
    cfg = load_config(CFG)
    seen = {}

    def fake(cmd, stdin, cwd, env, timeout):
        seen.update(cmd=cmd, stdin=stdin, env=env)
        out = {
            "is_error": False,
            "result": '{"tracked":[{"brand_id":"practice-d","rank":1}],"other_businesses":["X Dental"]}',
        }
        return ProcResult(0, json.dumps(out), "")

    monkeypatch.setattr("shutil.which", lambda name: "claude")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-should-not-leak")
    v = claude_cli_judge(cfg.brands, runner=fake)("Some answer")
    assert v.tracked == {"practice-d": 1} and v.others == ["X Dental"]
    cmd = seen["cmd"]
    assert cmd[cmd.index("--tools") + 1] == "" and "--no-session-persistence" in cmd
    assert "ANTHROPIC_API_KEY" not in seen["env"] and seen["env"]["CLAUDE_CODE_DISABLE_CLAUDE_MDS"] == "1"
    assert "practice-d" in seen["stdin"]


def test_evaluate_real_regex_judge_either_both():
    cfg = load_config(CFG)
    gold = [
        {"id": "a", "answer": "Practice D Dental is good.", "cited_urls": [], "mentioned": ["practice-d"]},
        {"id": "b", "answer": "The smile practice on Main Street.", "cited_urls": [], "mentioned": ["practice-c"]},
        {"id": "c", "answer": "Nothing here.", "cited_urls": [], "mentioned": []},
    ]
    verdicts = {"a": {"practice-d"}, "b": {"practice-c"}, "c": {"practice-e"}}
    res = evaluate_real(gold, cfg.brands, verdicts)
    assert res["regex"]["tp"] == 1 and res["regex"]["fn"] == 1 and res["regex"]["fp"] == 0
    assert res["judge"]["tp"] == 2 and res["judge"]["fp"] == 1
    assert res["either"]["tp"] == 2 and res["both"]["tp"] == 1 and res["both"]["fp"] == 0
    assert res["n_judged"] == 3 and res["n_true_mentions"] == 2
