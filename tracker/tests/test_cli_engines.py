"""Subscription-CLI engines, import mode and the serial runner. CLI output is faked; no CLI is called."""

import json
from pathlib import Path

import pytest

from vistrack import db, runner
from vistrack.analysis import build, heuristic_names
from vistrack.config import Market, load_config
from vistrack.engines.base import RawResult
from vistrack.engines.claude_cli_engine import ClaudeCliEngine
from vistrack.engines.cli_common import ProcResult
from vistrack.engines.codex_engine import CodexCliEngine
from vistrack.extract import urls_in_text
from vistrack.import_answers import import_jsonl
from vistrack.report import render

ROOT = Path(__file__).resolve().parent.parent
MARKET = Market("Austin", "Texas", "US", "America/Chicago", 30.27, -97.74, "Austin,Texas,United States")


def jl(*events):
    return "\n".join(json.dumps(e) for e in events) + "\n"


CODEX_OK = jl(
    {"type": "thread.started", "thread_id": "t"},
    {
        "type": "item.completed",
        "item": {
            "type": "web_search",
            "action": {"type": "search", "query": "q"},
            "results": [{"url": "https://yelp.com/a", "title": "Y"}, {"url": "https://other.com/", "title": "O"}],
        },
    },
    {
        "type": "item.completed",
        "item": {
            "type": "agent_message",
            "text": "Try **Practice D Dental** ([site](https://practice-d.example/?utm_source=openai)). See https://yelp.com/a.",
        },
    },
    {"type": "turn.completed", "usage": {"input_tokens": 100, "output_tokens": 20}},
)


def test_urls_in_text():
    assert urls_in_text("a [x](https://a.com/p?q=1) and https://b.com/z. Also https://a.com/p?q=1") == [
        "https://a.com/p?q=1",
        "https://b.com/z",
    ]


def test_codex_parse_ok():
    r = CodexCliEngine().parse(ProcResult(0, CODEX_OK, ""), "sent")
    assert r.status == "ok" and "Practice D" in r.answer_text and r.searches == 1
    assert r.tokens_in == 100 and r.cost_usd == 0
    kinds = {c.url: c.kind for c in r.citations}
    assert kinds["https://practice-d.example/?utm_source=openai"] == "cited"
    assert kinds["https://yelp.com/a"] == "cited" and kinds["https://other.com/"] == "consulted"


@pytest.mark.parametrize(
    "msg,fatal",
    [
        ("You've hit your usage limit. Try again at 5:00 PM", True),
        ("401 Unauthorized: not logged in", True),
        ("connection reset by peer", False),
    ],
)
def test_codex_failures_are_classified(msg, fatal):
    events = jl({"type": "error", "message": msg})
    r = CodexCliEngine().parse(ProcResult(1, events, ""))
    assert r.status == "error" and r.fatal is fatal and r.retryable is (not fatal)


def test_codex_command_is_read_only_search_with_location_in_prompt(monkeypatch):
    seen = {}

    def fake(cmd, stdin, cwd, env, timeout):
        seen.update(cmd=cmd, stdin=stdin, env=env)
        return ProcResult(0, CODEX_OK, "")

    monkeypatch.setattr("shutil.which", lambda name: "codex")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-should-not-leak")
    r = CodexCliEngine(runner=fake).query("best dentist in Austin TX", MARKET)
    assert r.status == "ok"
    cmd = seen["cmd"]
    assert cmd[:3] == ["codex", "--search", "exec"] and cmd[cmd.index("--sandbox") + 1] == "read-only"
    assert "--ephemeral" in cmd and not any("dangerous" in c or "workspace-write" in c for c in cmd)
    assert seen["stdin"].endswith("I'm in Austin, Texas.") and "OPENAI_API_KEY" not in seen["env"]


CLAUDE_OK = jl(
    {"type": "system", "subtype": "init"},
    {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "WebSearch", "input": {"query": "q"}}]}},
    {
        "type": "user",
        "message": {
            "content": [
                {
                    "type": "tool_result",
                    "content": 'Web search results for query: "q"\n\nLinks: [{"title":"Z","url":"https://zocdoc.com/x"}]\n\nSummary',
                }
            ]
        },
    },
    {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": "Practice A Smiles is an option.",
        "usage": {"input_tokens": 50, "output_tokens": 9},
        "modelUsage": {"claude-haiku-x": {}},
        "total_cost_usd": 0.01,
    },
)


def test_claude_parse_ok_and_cost_not_counted():
    r = ClaudeCliEngine().parse(ProcResult(0, CLAUDE_OK, ""))
    assert r.status == "ok" and r.searches == 1 and r.cost_usd == 0
    assert r.raw["model_reported"] == ["claude-haiku-x"]
    assert [(c.url, c.kind) for c in r.citations] == [("https://zocdoc.com/x", "consulted")]


def test_claude_auth_failure_is_fatal():
    out = jl({"type": "result", "is_error": True, "result": "Failed to authenticate: OAuth session expired"})
    r = ClaudeCliEngine().parse(ProcResult(1, out, ""))
    assert r.status == "error" and r.fatal


def test_claude_command_and_env_are_clean(monkeypatch):
    seen = {}

    def fake(cmd, stdin, cwd, env, timeout):
        seen.update(cmd=cmd, env=env, cwd=cwd, was_empty=not any(Path(cwd).iterdir()))
        return ProcResult(0, CLAUDE_OK, "")

    monkeypatch.setattr("shutil.which", lambda name: "claude")
    monkeypatch.setenv("CLAUDE_CODE_SIMPLE", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-should-not-leak")
    ClaudeCliEngine(runner=fake).query("best dentist in Austin TX", MARKET)
    cmd, env = seen["cmd"], seen["env"]
    assert cmd[cmd.index("--tools") + 1] == "WebSearch,WebFetch"
    assert cmd[cmd.index("--setting-sources") + 1] == "project"
    assert "--system-prompt" in cmd and "--strict-mcp-config" in cmd and "--disable-slash-commands" in cmd
    assert "CLAUDE_CODE_SIMPLE" not in env and "ANTHROPIC_API_KEY" not in env
    assert env["CLAUDE_CODE_DISABLE_CLAUDE_MDS"] == "1"
    assert seen["was_empty"] and not Path(seen["cwd"]).exists()  # empty during the call, removed afterwards


def test_claude_logged_out_is_reported(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "claude")
    eng = ClaudeCliEngine(runner=lambda *a: ProcResult(1, '{"loggedIn": false}', ""))
    assert "not logged in" in eng.missing_env()[0]


class Quota(CodexCliEngine):
    def __init__(self):
        super().__init__(model="m")
        self.calls = 0

    def missing_env(self):
        return []

    def query(self, prompt, market):
        self.calls += 1
        if self.calls == 3:
            return RawResult(status="error", error="usage limit", fatal=True)
        return RawResult(answer_text="Practice D Dental", raw={"n": self.calls})


def test_serial_engine_pauses_and_stops_on_quota(monkeypatch, tmp_path):
    cfg = load_config(ROOT / "config" / "austin_real.yaml")
    sleeps = []
    monkeypatch.setattr(runner.time, "sleep", sleeps.append)
    eng = Quota()
    eng.pause_seconds = 20.0
    conn = db.connect(tmp_path / "t.db")
    s = runner.run_batch(cfg, [eng], conn, batch="b", reps=5, budget_usd=25, raw_dir=tmp_path / "raw", backoff=0.0)
    assert eng.calls == 3 and s.ok == 2 and s.errors == 1 and s.stopped_early
    assert sleeps == [20.0, 20.0]
    assert "fatal" in s.notes[0]
    assert conn.execute("SELECT COUNT(*) FROM run WHERE status='ok'").fetchone()[0] == 2  # kept what we had


def test_per_engine_reps_override(monkeypatch, tmp_path):
    cfg = load_config(ROOT / "config" / "austin_real.yaml")
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)
    eng = Quota()
    eng.reps = 1
    eng.calls = 10  # never hits the quota call
    conn = db.connect(tmp_path / "t.db")
    s = runner.run_batch(cfg, [eng], conn, batch="b", reps=5, budget_usd=25, raw_dir=tmp_path / "raw", backoff=0.0)
    assert s.ok == len(cfg.prompts)


def test_import_jsonl_and_report(tmp_path):
    cfg = load_config(ROOT / "config" / "austin_real.yaml")
    f = tmp_path / "apps.jsonl"
    f.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "prompt": "Best dentist in Austin TX",
                        "app": "ChatGPT",
                        "date": "2026-11-02",
                        "text": "Try Practice D Dental. https://www.practice-d.example/x",
                    }
                ),
                json.dumps(
                    {
                        "prompt": "best dentist in austin tx",
                        "app": "ChatGPT",
                        "date": "2026-11-03",
                        "text": "Practice A Smiles.",
                    }
                ),
                json.dumps(
                    {
                        "prompt": "a prompt not in the config",
                        "app": "Gemini",
                        "date": "2026-11-03",
                        "text": "Practice E Dentistry",
                    }
                ),
                "not json",
                json.dumps({"prompt": "p", "app": "x", "date": "d", "text": "  "}),
            ]
        ),
        encoding="utf-8",
    )
    conn = db.connect(tmp_path / "t.db")
    s = import_jsonl(conn, cfg, f, "b", tmp_path / "raw")
    assert s.imported == 3 and len(s.skipped) == 2
    rows = conn.execute("SELECT engine, prompt_id, rep_index, model, executed_at FROM run ORDER BY id").fetchall()
    assert [(r["engine"], r["prompt_id"], r["rep_index"]) for r in rows[:2]] == [
        ("app_chatgpt", "p01", 1),
        ("app_chatgpt", "p01", 2),
    ]
    assert (
        rows[2]["prompt_id"].startswith("x-")
        and "by hand" in rows[0]["model"]
        and rows[0]["executed_at"] == "2026-11-02"
    )
    assert conn.execute("SELECT COUNT(*) FROM citation WHERE brand_id='practice-d'").fetchone()[0] == 1
    html = render(conn, cfg, "b", tmp_path / "r.html").read_text(encoding="utf-8")
    assert "Chatgpt app (pasted by hand)" in html
    assert "None of these is the consumer app" in html
    data = build(conn, cfg, "b")
    assert data["rates"]["practice-d"]["app_chatgpt"]["k"] == 1


def test_heuristic_names_skips_tracked_and_noise():
    cfg = load_config(ROOT / "config" / "austin_real.yaml")
    text = (
        "**Elm Street Dental** is big. **Practice D Dental** too. [ATX Family Dental](https://x.com/) works. "
        "**Pricing:** varies. **Best** overall. See [Source](https://y.com)."
    )
    assert heuristic_names(text, cfg.brands) == {"Elm Street Dental", "ATX Family Dental"}
