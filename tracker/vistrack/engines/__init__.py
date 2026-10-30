"""Engine registry. Gemini grounding is intentionally absent: its terms forbid storing/analysing results."""

from __future__ import annotations

import httpx

from ..config import Config
from .anthropic_engine import AnthropicEngine
from .base import Engine
from .claude_cli_engine import ClaudeCliEngine
from .codex_engine import CodexCliEngine
from .dataforseo_engine import GoogleAiModeEngine, GoogleAioEngine
from .mock import MockEngine
from .openai_engine import OpenAIEngine
from .perplexity_engine import PerplexityEngine

ENGINE_CLASSES: dict[str, type[Engine]] = {
    c.key: c
    for c in (
        OpenAIEngine,
        AnthropicEngine,
        PerplexityEngine,
        GoogleAioEngine,
        GoogleAiModeEngine,
        CodexCliEngine,
        ClaudeCliEngine,
    )
}
MOCKABLE = ("openai", "anthropic", "perplexity", "google_aio", "google_ai_mode")


def build_engines(
    cfg: Config,
    *,
    mock: bool = False,
    only: list[str] | None = None,
    client: httpx.Client | None = None,
    seed: int = 0,
    check_env: bool = True,
) -> tuple[list[Engine], dict[str, str]]:
    """Returns (enabled engines, {engine_key: reason it is disabled}).

    Only engines listed in the config's `engines:` section are considered.
    check_env=False keeps engines whose keys/logins are missing (cost estimates only); the reason
    is still reported in the second value.
    """
    engines: list[Engine] = []
    disabled: dict[str, str] = {}
    for key, cls in ENGINE_CLASSES.items():
        if key not in cfg.engines or (only and key not in only):
            continue
        opts = cfg.engines[key] or {}
        if not opts.get("enabled", True):
            disabled[key] = "disabled in config"
            continue
        if mock:
            if key in MOCKABLE:
                engines.append(MockEngine(cls, list(cfg.brands), list(cfg.mock.get("fillers", [])), seed))
            else:
                disabled[key] = "no mock for CLI engines"
            continue
        engine = cls(model=opts.get("model"), params=opts.get("params"), client=client, reps=opts.get("reps"))
        missing = engine.missing_env()
        if missing:
            disabled[key] = "missing: " + ", ".join(missing)
            if check_env:
                continue
        engines.append(engine)
    return engines, disabled
