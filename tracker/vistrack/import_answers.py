"""Import answers pasted by hand from consumer apps, to compare API/CLI answers with the apps later.

JSONL, one answer per line:
  {"prompt": "best dentist in Austin TX", "app": "chatgpt", "date": "2026-11-02",
   "text": "<the answer as shown>", "urls": ["https://..."], "location": "Austin, TX (device)"}
`date` must be ISO (YYYY-MM-DD or a full ISO timestamp). `urls` and `location` are optional; URLs
written inside `text` are picked up too. Each (prompt, app) can have several different answers: they become
repetitions 1, 2, 3... Importing the same file again adds nothing (an identical answer for the same
prompt and app is skipped).
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date as _date
from datetime import datetime
from pathlib import Path

from .config import Config
from .engines.base import Citation, RawResult
from .extract import normalize, urls_in_text
from .runner import _store_result

APP_LABEL = "consumer app (answer pasted by hand)"
DEFAULT_LOCATION = "as set in the app (not controlled)"


@dataclass
class ImportedApp:
    key: str
    model: str = APP_LABEL
    tool_version: str = "manual"
    est_cost_upper: float = 0.0


@dataclass
class ImportSummary:
    imported: int = 0
    duplicates: int = 0
    skipped: list[str] = field(default_factory=list)


def engine_key(app: str) -> str:
    return "app_" + re.sub(r"[^a-z0-9]+", "_", app.lower()).strip("_")


def iso_date(value: object) -> str:
    """Normalise to ISO so min/max over executed_at stays meaningful; raises ValueError otherwise."""
    text = str(value).strip()
    try:
        return _date.fromisoformat(text).isoformat()
    except ValueError:
        return datetime.fromisoformat(text).isoformat(timespec="seconds")


def _text_hash(text: str) -> str:
    return hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()


def import_jsonl(conn: sqlite3.Connection, cfg: Config, path: str | Path, batch: str, raw_dir: Path) -> ImportSummary:
    by_text = {normalize(p.text): p.id for p in cfg.prompts}
    summary = ImportSummary()
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            prompt, app, text = row["prompt"], row["app"], row["text"]
            executed_at = iso_date(row["date"])
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            summary.skipped.append(f"line {n}: {type(exc).__name__} {exc}")
            continue
        if not str(text).strip():
            summary.skipped.append(f"line {n}: empty text")
            continue
        pid = by_text.get(normalize(prompt)) or "x-" + hashlib.sha1(normalize(prompt).encode()).hexdigest()[:6]
        key = engine_key(app)
        same = conn.execute(
            "SELECT answer_text FROM run WHERE batch=? AND prompt_id=? AND engine=?", (batch, pid, key)
        ).fetchall()
        if any(_text_hash(r["answer_text"] or "") == _text_hash(text) for r in same):
            summary.duplicates += 1
            continue
        urls = list(dict.fromkeys([*row.get("urls", []), *urls_in_text(text)]))
        result = RawResult(
            answer_text=text, citations=[Citation(u, None, i, "cited") for i, u in enumerate(urls, 1)], raw=row
        )
        prompt_obj = type("P", (), {"id": pid, "text": prompt})()
        _store_result(
            cfg,
            conn,
            ImportedApp(key),
            prompt_obj,
            len(same) + 1,
            result,
            batch,
            False,
            raw_dir,
            None,
            executed_at=executed_at,
            location=row.get("location") or DEFAULT_LOCATION,
        )
        summary.imported += 1
    conn.commit()
    return summary
