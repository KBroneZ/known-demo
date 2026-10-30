"""Run `claude -p` as an isolated, tool-less text generator and record what it cost.

Isolation matters: a user-level CLAUDE.md can force a language or style into the output. The call therefore
disables memory, skills, MCP and tools, runs in an empty directory, and sets its own system prompt.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass


class ClaudeError(RuntimeError):
    def __init__(self, message: str, cost_usd: float = 0.0):
        super().__init__(message)
        self.cost_usd = cost_usd  # what the failed call still cost, when the CLI reported it


@dataclass(frozen=True)
class Call:
    stage: str
    model: str
    text: str
    cost_usd: float
    seconds: float
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int

    def record(self) -> dict:
        return {
            "stage": self.stage,
            "model": self.model,
            "cost_usd": round(self.cost_usd, 5),
            "seconds": round(self.seconds, 1),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
        }


def build_command(exe: str, model: str, system: str, max_budget_usd: float) -> list[str]:
    return [
        exe,
        "-p",
        "--tools",
        "",
        "--no-session-persistence",
        "--max-budget-usd",
        f"{max_budget_usd:.2f}",
        "--disable-slash-commands",
        "--setting-sources",
        "",
        "--strict-mcp-config",
        "--system-prompt",
        system,
        "--output-format",
        "json",
        "--model",
        model,
    ]


def parse_output(raw: str) -> tuple[str, float, dict]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ClaudeError(f"claude printed non-JSON output: {raw[:200]!r}") from exc
    if not isinstance(data, dict):
        raise ClaudeError("claude JSON output is not an object")
    if data.get("is_error"):
        raise ClaudeError(
            f"claude reported an error: {str(data.get('result'))[:300]}", float(data.get("total_cost_usd") or 0.0)
        )
    return str(data.get("result", "")), float(data.get("total_cost_usd") or 0.0), data.get("usage") or {}


def call(stage: str, prompt: str, model: str, system: str, timeout: int = 420, max_budget_usd: float = 0.60) -> Call:
    exe = shutil.which("claude")
    if not exe:
        raise ClaudeError("claude CLI not found on PATH")
    started = time.perf_counter()
    with tempfile.TemporaryDirectory() as empty_cwd:
        try:
            proc = subprocess.run(
                build_command(exe, model, system, max_budget_usd),
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=timeout,
                cwd=empty_cwd,
                env={**os.environ, "CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1"},
            )
        except subprocess.TimeoutExpired as exc:
            raise ClaudeError(f"claude timed out after {timeout}s at stage {stage}") from exc
    elapsed = time.perf_counter() - started
    if proc.returncode != 0 and not proc.stdout.strip():
        raise ClaudeError(f"claude exited {proc.returncode}: {proc.stderr.strip()[-300:]}")
    text, cost, usage = parse_output(proc.stdout)
    if not text.strip():
        raise ClaudeError(f"claude returned an empty answer at stage {stage}")
    return Call(
        stage,
        model,
        text,
        cost,
        elapsed,
        int(usage.get("input_tokens", 0)),
        int(usage.get("output_tokens", 0)),
        int(usage.get("cache_read_input_tokens", 0)),
    )
