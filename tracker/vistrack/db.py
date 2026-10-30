"""SQLite storage: one row per run, plus extracted mentions and citations."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS run (
    id INTEGER PRIMARY KEY,
    batch TEXT NOT NULL,
    is_mock INTEGER NOT NULL DEFAULT 0,
    prompt_id TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    engine TEXT NOT NULL,
    model TEXT NOT NULL,
    tool_version TEXT,
    location TEXT NOT NULL,
    rep_index INTEGER NOT NULL,
    executed_at TEXT NOT NULL,
    status TEXT NOT NULL,              -- ok | error  (errors never enter denominators)
    answer_present INTEGER NOT NULL DEFAULT 1,  -- 0 = e.g. no AI Overview shown
    error TEXT,
    http_status INTEGER,
    latency_ms INTEGER,
    cost_usd REAL NOT NULL DEFAULT 0,
    tokens_in INTEGER,
    tokens_out INTEGER,
    searches INTEGER,
    raw_path TEXT,
    raw_sha256 TEXT,
    answer_text TEXT
);
CREATE INDEX IF NOT EXISTS run_cell ON run (batch, prompt_id, engine, rep_index);

CREATE TABLE IF NOT EXISTS mention (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES run(id),
    brand_id TEXT NOT NULL,
    first_offset INTEGER,
    position INTEGER,                  -- order among tracked brands named (1 = first)
    matched_by TEXT NOT NULL,          -- regex | judge | both
    negative INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS mention_run ON mention (run_id);

CREATE TABLE IF NOT EXISTS citation (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES run(id),
    rank INTEGER,
    kind TEXT NOT NULL,                -- cited | consulted
    url TEXT NOT NULL,
    domain TEXT,
    title TEXT,
    brand_id TEXT                      -- set when the domain belongs to a tracked brand
);
CREATE INDEX IF NOT EXISTS citation_run ON citation (run_id);

CREATE TABLE IF NOT EXISTS judge_verdict (    -- one LLM-judge verdict per run (raw JSON kept)
    run_id INTEGER PRIMARY KEY REFERENCES run(id),
    judge TEXT NOT NULL,
    verdict_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS other_business (   -- judge only: untracked names
    run_id INTEGER NOT NULL REFERENCES run(id),
    name TEXT NOT NULL
);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def insert_run(conn: sqlite3.Connection, row: dict) -> int:
    cols = ", ".join(row)
    marks = ", ".join(f":{k}" for k in row)
    cur = conn.execute(f"INSERT INTO run ({cols}) VALUES ({marks})", row)
    return int(cur.lastrowid)


def insert_mentions(conn: sqlite3.Connection, run_id: int, rows: list[dict]) -> None:
    conn.executemany(
        "INSERT INTO mention (run_id, brand_id, first_offset, position, matched_by, negative) "
        "VALUES (:run_id, :brand_id, :first_offset, :position, :matched_by, :negative)",
        [{**r, "run_id": run_id} for r in rows],
    )


def insert_citations(conn: sqlite3.Connection, run_id: int, rows: list[dict]) -> None:
    conn.executemany(
        "INSERT INTO citation (run_id, rank, kind, url, domain, title, brand_id) "
        "VALUES (:run_id, :rank, :kind, :url, :domain, :title, :brand_id)",
        [{**r, "run_id": run_id} for r in rows],
    )


def insert_other_businesses(conn: sqlite3.Connection, run_id: int, names: list[str]) -> None:
    conn.executemany(
        "INSERT INTO other_business (run_id, name) VALUES (?, ?)",
        [(run_id, n) for n in names],
    )


def done_cells(conn: sqlite3.Connection, batch: str) -> set[tuple[str, str, int]]:
    """(prompt_id, engine, rep_index) already completed OK in this batch."""
    rows = conn.execute(
        "SELECT prompt_id, engine, rep_index FROM run WHERE batch = ? AND status = 'ok'", (batch,)
    ).fetchall()
    return {(r["prompt_id"], r["engine"], r["rep_index"]) for r in rows}


def batch_cost(conn: sqlite3.Connection, batch: str) -> float:
    row = conn.execute("SELECT COALESCE(SUM(cost_usd), 0) AS c FROM run WHERE batch = ?", (batch,)).fetchone()
    return float(row["c"])
