from pathlib import Path

import pytest

from vistrack import db
from vistrack.analysis import build
from vistrack.config import load_config
from vistrack.cost import BudgetExceeded, check_plan, estimate
from vistrack.engines import build_engines
from vistrack.engines.base import Engine, RawResult
from vistrack.judge import JudgeVerdict, parse_verdict, reconcile
from vistrack.report import render
from vistrack.runner import run_batch

ROOT = Path(__file__).resolve().parent.parent
MOCK_CFG = ROOT / "config" / "mock_demo.yaml"


@pytest.fixture
def cfg():
    return load_config(MOCK_CFG)


def mock_run(cfg, tmp_path, reps=2, **kw):
    engines, _ = build_engines(cfg, mock=True)
    conn = db.connect(tmp_path / "t.db")
    summary = run_batch(
        cfg,
        engines,
        conn,
        batch="b",
        reps=reps,
        budget_usd=25,
        raw_dir=tmp_path / "raw",
        is_mock=True,
        backoff=0.0,
        **kw,
    )
    return conn, summary, engines


def test_mock_batch_end_to_end(cfg, tmp_path):
    conn, summary, engines = mock_run(cfg, tmp_path)
    assert summary.ok + summary.errors == len(cfg.prompts) * len(engines) * 2
    assert conn.execute("SELECT COUNT(*) FROM run WHERE is_mock = 0").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM mention").fetchone()[0] > 0
    row = conn.execute("SELECT raw_path, raw_sha256 FROM run WHERE raw_path IS NOT NULL").fetchone()
    assert Path(row["raw_path"]).exists() and Path(row["raw_path"]).stem == row["raw_sha256"]


def test_rerun_skips_completed_cells(cfg, tmp_path):
    conn, first, engines = mock_run(cfg, tmp_path)
    second = run_batch(
        cfg, engines, conn, batch="b", reps=2, budget_usd=25, raw_dir=tmp_path / "raw", is_mock=True, backoff=0.0
    )
    assert second.skipped_done == first.ok
    assert second.ok + second.errors == first.errors  # only previously failed cells are retried


def test_errors_and_absent_answers_are_excluded_from_denominators(cfg, tmp_path):
    conn, _, _ = mock_run(cfg, tmp_path, reps=4)
    data = build(conn, cfg, "b")
    for e in data["engines"]:
        s = data["engine_summary"][e]
        assert s["scored"] == s["ok"] - s["no_answer"]
        for b in cfg.brands:
            assert data["rates"][b.id][e]["n"] == s["scored"]
    assert data["engine_summary"]["google_aio"]["no_answer"] > 0  # mock hides most AI Overviews


def test_report_renders_with_mock_banner(cfg, tmp_path):
    conn, _, _ = mock_run(cfg, tmp_path)
    out = render(conn, cfg, "b", tmp_path / "r" / "index.html")
    html = out.read_text(encoding="utf-8")
    assert "SYNTHETIC DATA" in html and "Cedar Hollow Dental" in html and "Wilson" in html


class Costly(Engine):
    key, label, est_cost_upper = "openai", "costly", 1.0

    def available(self):
        return True

    def query(self, prompt, market):
        return RawResult(answer_text="x", cost_usd=1.0, raw={"x": 1})


def test_plan_over_budget_aborts_before_any_call(cfg, tmp_path):
    engines = [Costly()]
    est = estimate(cfg, engines, reps=5)
    assert est.upper_usd == 50.0
    with pytest.raises(BudgetExceeded):
        check_plan(est, 25)
    conn = db.connect(tmp_path / "t.db")
    with pytest.raises(BudgetExceeded):
        run_batch(cfg, engines, conn, batch="b", reps=5, budget_usd=25, raw_dir=tmp_path / "raw", backoff=0.0)
    assert conn.execute("SELECT COUNT(*) FROM run").fetchone()[0] == 0


def test_spend_stops_at_budget_mid_run(cfg, tmp_path):
    engines = [Costly()]
    conn = db.connect(tmp_path / "t.db")
    summary = run_batch(cfg, engines, conn, batch="b", reps=2, budget_usd=20, raw_dir=tmp_path / "raw", backoff=0.0)
    assert summary.stopped_early
    assert summary.spent_usd <= 20 + 1e-9


class Flaky(Engine):
    key, label, est_cost_upper = "openai", "flaky", 0.0

    def __init__(self):
        super().__init__(model="m", client=None)
        self.calls = 0

    def available(self):
        return True

    def query(self, prompt, market):
        self.calls += 1
        if self.calls % 2:
            return RawResult(status="error", error="429", retryable=True, http_status=429)
        return RawResult(answer_text="Cedar Hollow Dental", raw={"ok": 1})


def test_retryable_errors_are_retried(cfg, tmp_path):
    conn = db.connect(tmp_path / "t.db")
    eng = Flaky()
    summary = run_batch(
        cfg, [eng], conn, batch="b", reps=1, budget_usd=25, raw_dir=tmp_path / "raw", backoff=0.0, workers=1
    )
    assert summary.ok == len(cfg.prompts) and summary.errors == 0
    assert eng.calls == 2 * len(cfg.prompts)


def test_judge_parse_and_reconcile(cfg):
    verdict = parse_verdict(
        'noise {"tracked":[{"brand_id":"oakline","rank":2},{"brand_id":"nope","rank":1}],'
        '"other_businesses":["Other Dental"]} tail',
        cfg.brands,
    )
    assert verdict.tracked == {"oakline": 2} and verdict.others == ["Other Dental"]
    assert reconcile({"oakline", "cedar-hollow"}, verdict) == {"oakline": "both", "cedar-hollow": "regex"}
    assert reconcile(set(), JudgeVerdict({"oakline": 1}, [])) == {"oakline": "judge"}
    with pytest.raises(ValueError):
        parse_verdict("no json here", cfg.brands)
