"""Claude Haiku with web search, driven through the Claude Code CLI (`claude -p`, subscription login).

This is a coding-agent CLI, not claude.ai and not the API. To keep the sample clean the call:
- uses a minimal custom system prompt (replaces Claude Code's own),
- loads no user/project settings (`--setting-sources project` in an empty temp dir), no MCP servers,
  no slash commands/skills, no hooks from user settings,
- sets CLAUDE_CODE_DISABLE_CLAUDE_MDS=1 so ~/.claude/CLAUDE.md and rules are not injected,
- exposes only WebSearch and WebFetch,
- drops every inherited CLAUDE_CODE_* variable (a parent Claude Code session sets
  CLAUDE_CODE_SIMPLE, which switches OAuth login off).
Location is only the sentence "I'm in <city>, <state>." appended to the prompt.
"""

from __future__ import annotations

import contextlib
import json
import re
import shutil
import time
from pathlib import Path

from ..config import Market
from ..extract import urls_in_text
from .base import Citation, Engine, RawResult, dedupe_citations, error_result
from .cli_common import ProcResult, Runner, allowlist_env, classify_failure, empty_workdir, run_subprocess

TIMEOUT_S = 300
SYSTEM_PROMPT = "You are a helpful assistant. Use web search when it helps answer the question."
_LINKS = re.compile(r"Links:\s*(\[.*?\])\s*(?:\n|$)", re.S)


def _env() -> dict[str, str]:
    """Allowlisted environment (no secrets, no inherited CLAUDE_CODE_* from a parent session)."""
    return allowlist_env({"CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1", "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"})


class ClaudeCliEngine(Engine):
    key = "claude_cli"
    label = "Claude Haiku via Claude Code CLI (web search)"
    tool_version = "claude -p WebSearch,WebFetch"
    est_cost_upper = 0.0  # subscription quota, not dollars
    default_model = "haiku"
    serial = True
    pause_seconds = 20.0

    def __init__(self, *args, runner: Runner = run_subprocess, **kw) -> None:
        super().__init__(*args, **kw)
        self.runner = runner
        self.pause_seconds = float(self.params.get("pause_seconds", self.pause_seconds))

    def missing_env(self) -> list[str]:
        exe = shutil.which("claude")
        if not exe:
            return ["claude CLI not on PATH"]
        res = self.runner([exe, "auth", "status"], "", Path.cwd(), _env(), 30)
        try:
            logged_in = bool(json.loads(res.stdout).get("loggedIn"))
        except (json.JSONDecodeError, AttributeError):
            logged_in = False
        return [] if logged_in else ["claude CLI not logged in (run: claude auth login)"]

    def command(self, exe: str) -> list[str]:
        return [
            exe,
            "-p",
            "--model",
            self.model,
            "--tools",
            "WebSearch,WebFetch",
            "--allowedTools",
            "WebSearch,WebFetch",
            "--setting-sources",
            "project",
            "--strict-mcp-config",
            "--disable-slash-commands",
            "--no-session-persistence",
            "--system-prompt",
            SYSTEM_PROMPT,
            "--output-format",
            "stream-json",
            "--verbose",
        ]

    def query(self, prompt: str, market: Market) -> RawResult:
        exe = shutil.which("claude")
        if not exe:
            return error_result("claude CLI not on PATH", retryable=False, fatal=True)
        sent = f"{prompt}\n\nI'm in {market.city}, {market.region}."
        t0 = time.monotonic()
        with empty_workdir("vistrack-claude-") as workdir:
            res = self.runner(self.command(exe), sent, workdir, _env(), TIMEOUT_S)
        ms = int((time.monotonic() - t0) * 1000)
        if res.timed_out:
            return error_result("claude timed out", retryable=True, latency_ms=ms)
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
            "events": events,
            "stderr": res.stderr[-2000:],
            "returncode": res.returncode,
        }
        final = next((e for e in reversed(events) if e.get("type") == "result"), None)
        if final is None or final.get("is_error") or res.returncode != 0:
            blob = ((final or {}).get("result") or "") + "\n" + res.stderr
            fatal, why = classify_failure(blob)
            msg = (f"claude {why} error: " if fatal else "claude failed: ") + blob.strip()[:300]
            return error_result(msg, retryable=not fatal, raw=raw, latency_ms=latency_ms, fatal=fatal)
        text = final.get("result") or ""
        if not text.strip():  # a blank answer is a failed call, not a "not mentioned"
            return error_result("claude returned an empty answer", retryable=True, raw=raw, latency_ms=latency_ms)
        searches, consulted = 0, []
        for ev in events:
            content_blocks = (ev.get("message") or {}).get("content")
            if not isinstance(content_blocks, list):
                continue
            for block in content_blocks:
                if not isinstance(block, dict):
                    continue
                if (
                    ev.get("type") == "assistant"
                    and block.get("type") == "tool_use"
                    and block.get("name") == "WebSearch"
                ):
                    searches += 1
                if ev.get("type") == "user" and block.get("type") == "tool_result":
                    content = block.get("content")
                    if isinstance(content, list):
                        content = "\n".join(c.get("text", "") for c in content if isinstance(c, dict))
                    consulted += self._links(str(content or ""))
        cited = [Citation(u, None, kind="cited") for u in urls_in_text(text)]
        cited_urls = {c.url for c in cited}
        extra = [c for c in consulted if c.url not in cited_urls]
        usage = final.get("usage") or {}
        models = sorted((final.get("modelUsage") or {}).keys())
        if models:
            raw["model_reported"] = models
        return RawResult(
            status="ok",
            answer_text=text,
            citations=dedupe_citations(cited + extra),
            raw=raw,
            latency_ms=latency_ms,
            tokens_in=usage.get("input_tokens"),
            tokens_out=usage.get("output_tokens"),
            searches=searches,
            cost_usd=0.0,  # total_cost_usd is a notional figure under a subscription
        )

    @staticmethod
    def _links(text: str) -> list[Citation]:
        m = _LINKS.search(text)
        if not m:
            return []
        try:
            items = json.loads(m.group(1))
        except json.JSONDecodeError:
            return []
        return [
            Citation(i["url"], i.get("title"), kind="consulted") for i in items if isinstance(i, dict) and i.get("url")
        ]
