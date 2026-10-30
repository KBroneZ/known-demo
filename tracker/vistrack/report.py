"""Render the static HTML report."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .analysis import build
from .anonymize import anonymize_config, remap_data
from .config import Config

ENGINE_LABELS = {
    "codex_cli": "OpenAI model via Codex CLI",
    "claude_cli": "Claude Haiku via Claude Code CLI",
    "openai": "ChatGPT (OpenAI API)",
    "anthropic": "Claude (Anthropic API)",
    "perplexity": "Perplexity (Agent API)",
    "google_aio": "Google AI Overviews (via DataForSEO)",
    "google_ai_mode": "Google AI Mode (via DataForSEO)",
}


ENGINE_NOTES = {
    "codex_cli": "An OpenAI model with its native web search, run through OpenAI's Codex coding-agent CLI "
    "under a ChatGPT Plus login "
    "(read-only sandbox, empty working directory). It is <b>not</b> the ChatGPT app and not the API. "
    "Location is only the sentence \"I'm in Austin, Texas.\" added to the prompt. Codex is a coding agent, so its "
    "style and search behaviour may differ from ChatGPT.",
    "claude_cli": "Claude Haiku with Claude's WebSearch and WebFetch tools, run through the Claude Code CLI "
    "under a Claude subscription, with the "
    "user's memory files, settings and plugins switched off and a minimal system prompt. "
    "It is <b>not</b> claude.ai and not the "
    "API. Location is only the sentence \"I'm in Austin, Texas.\" added to the prompt.",
    "openai": "OpenAI Responses API with the web_search tool and an approximate Austin location. Not the ChatGPT app.",
    "anthropic": "Anthropic Messages API with the web_search tool and an approximate Austin location. Not claude.ai.",
    "perplexity": "Perplexity Agent API with the web_search tool and an Austin location. Not the Perplexity app.",
    "google_aio": "Google AI Overviews as returned by DataForSEO, a third-party search-data provider, for Austin.",
    "google_ai_mode": "Google AI Mode as returned by DataForSEO, a third-party search-data provider, for Austin.",
}


def engine_label(key: str) -> str:
    if key in ENGINE_LABELS:
        return ENGINE_LABELS[key]
    if key.startswith("app_"):
        return key[4:].replace("_", " ").title() + " app (pasted by hand)"
    return key


def engine_note(key: str) -> str:
    if key in ENGINE_NOTES:
        return ENGINE_NOTES[key]
    if key.startswith("app_"):
        return (
            "Answers copied by hand from the consumer app, with the app's own location, history and settings. "
            "Few answers per prompt, so read it as an example, not a rate."
        )
    return ""


def _pct(x: float | None, digits: int = 0) -> str:
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x * 100:.{digits}f}%"


def _bar(x: float | None) -> str:
    return "0" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x * 100:.1f}"


def render(
    conn,
    cfg: Config,
    batch: str,
    out_path: str | Path,
    validation_path: str | Path | None = None,
    disabled: dict[str, str] | None = None,
    anonymize: bool = False,
) -> Path:
    data = build(conn, cfg, batch)
    if anonymize:
        data = remap_data(data, cfg)
        cfg = anonymize_config(cfg)
    validation = None
    if validation_path and Path(validation_path).exists():
        validation = json.loads(Path(validation_path).read_text(encoding="utf-8"))
    validation_real = None
    if validation_path:
        real_path = Path(validation_path).with_name("validation_real.json")
        if real_path.exists():
            validation_real = json.loads(real_path.read_text(encoding="utf-8"))
    env = Environment(
        loader=FileSystemLoader(Path(__file__).parent / "templates"),
        autoescape=select_autoescape(["html", "j2"]),
    )
    env.filters["pct"] = _pct
    env.filters["bar"] = _bar
    html = env.get_template("report.html.j2").render(
        d=data,
        cfg=cfg,
        brands={b.id: b for b in cfg.brands},
        labels={e: engine_label(e) for e in data["engines"]},
        notes={e: engine_note(e) for e in data["engines"]},
        validation=validation,
        validation_real=validation_real if not data["meta"]["is_mock"] else None,
        anonymized=anonymize,
        disabled=disabled or {},
        generated=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    )
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out
