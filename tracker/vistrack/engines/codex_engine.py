"""OpenAI model with native web search, driven through the Codex CLI (ChatGPT Plus login).

This is a coding-agent CLI, not the ChatGPT consumer app and not the API. Location is only
the sentence "I'm in <city>, <state>." appended to the prompt. Read-only sandbox, empty temp
working directory, ephemeral session. ~/.codex/config.toml only sets the default model and
effort (no AGENTS.md, memories feature off); we pass both explicitly anyway.
"""

from __future__ import annotations

import contextlib
import json
import shutil
import time
from pathlib import Path

from ..config import Market
from ..extract import urls_in_text
from .base import Citation, Engine, RawResult, dedupe_citations, error_result
from .cli_common import ProcResult, Runner, allowlist_env, classify_failure, empty_workdir, run_subprocess

TIMEOUT_S = 600


class CodexCliEngine(Engine):
    key = "codex_cli"
    label = "OpenAI model via Codex CLI (web search)"
    tool_version = "codex exec --search"
    est_cost_upper = 0.0  # subscription quota, not dollars
    default_model = "gpt-6-luna"
    serial = True
    pause_seconds = 20.0

    def __init__(self, *args, runner: Runner = run_subprocess, **kw) -> None:
        super().__init__(*args, **kw)
        self.runner = runner
        self.effort = self.params.get("effort", "medium")
        self.pause_seconds = float(self.params.get("pause_seconds", self.pause_seconds))

    def missing_env(self) -> list[str]:
        exe = shutil.which("codex")
        if not exe:
            return ["codex CLI not on PATH"]
        res = self.runner([exe, "login", "status"], "", Path.cwd(), allowlist_env(), 30)
        if res.returncode != 0:
            return ["codex not logged in (run: codex login)"]
        return []

    def command(self, exe: str, workdir: Path) -> list[str]:
        return [
            exe,
            "--search",
            "exec",
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            "--ephemeral",
            "--color",
            "never",
            "--json",
            "--disable",
            "memories",
            "--disable",
            "hooks",
            "-C",
            str(workdir),
            "-m",
            self.model,
            "-c",
            f'model_reasoning_effort="{self.effort}"',
            "-",
        ]

    def query(self, prompt: str, market: Market) -> RawResult:
        exe = shutil.which("codex")
        if not exe:
            return error_result("codex CLI not on PATH", retryable=False, fatal=True)
        sent = f"{prompt}\n\nI'm in {market.city}, {market.region}."
        t0 = time.monotonic()
        with empty_workdir("vistrack-codex-") as workdir:
            res = self.runner(self.command(exe, workdir), sent, workdir, allowlist_env(), TIMEOUT_S)
        ms = int((time.monotonic() - t0) * 1000)
        if res.timed_out:
            return error_result("codex timed out", retryable=True, latency_ms=ms)
        return self.parse(res, sent, ms)

    def parse(self, res: ProcResult, sent: str = "", latency_ms: int = 0) -> RawResult:
        events = []
        for line in res.stdout.splitlines():
            line = line.strip()
            if line.startswith("{"):
                with contextlib.suppress(json.JSONDecodeError):
                    events.append(json.loads(line))
        raw = {
            "sent_prompt": sent,
            "model_requested": self.model,
            "effort": self.effort,
            "events": events,
            "stderr": res.stderr[-2000:],
            "returncode": res.returncode,
        }
        answers, consulted, searches, usage, errors = [], [], 0, {}, []
        for ev in events:
            kind = ev.get("type")
            item = ev.get("item") or {}
            if kind == "item.completed" and item.get("type") == "agent_message":
                answers.append(item.get("text", ""))
            elif kind == "item.completed" and item.get("type") == "web_search":
                if (item.get("action") or {}).get("type") == "search":
                    searches += 1
                for r in item.get("results") or []:
                    if r.get("url"):
                        consulted.append(Citation(r["url"], r.get("title"), kind="consulted"))
            elif kind == "turn.completed":
                usage = ev.get("usage") or {}
            elif kind in ("error", "turn.failed"):
                errors.append(str(ev.get("message") or ev.get("error") or ev))
        if not answers or res.returncode != 0:
            blob = "\n".join(errors) + "\n" + res.stderr
            fatal, why = classify_failure(blob)
            msg = (f"codex {why} error: " if fatal else "codex failed: ") + blob.strip()[:300]
            return error_result(msg, retryable=not fatal, raw=raw, latency_ms=latency_ms, fatal=fatal)
        text = answers[-1]
        if not text.strip():  # a blank answer is a failed call, not a "not mentioned"
            return error_result("codex returned an empty answer", retryable=True, raw=raw, latency_ms=latency_ms)
        cited = [Citation(u, None, kind="cited") for u in urls_in_text(text)]
        cited_urls = {c.url for c in cited}
        extra = [c for c in consulted if c.url not in cited_urls]
        return RawResult(
            status="ok",
            answer_text=text,
            citations=dedupe_citations(cited + extra),
            raw=raw,
            latency_ms=latency_ms,
            tokens_in=usage.get("input_tokens"),
            tokens_out=usage.get("output_tokens"),
            searches=searches,
            cost_usd=0.0,
        )
