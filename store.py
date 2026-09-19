"""AppealMate — persistence. SQLite + append-only audit log + run counts."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).parent / "appealmate.db"

AUDIT_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    target TEXT NOT NULL,
    detail TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    app TEXT NOT NULL,
    outcome TEXT NOT NULL,
    session_id TEXT
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Auto-initialize so tests and first-run work without an explicit init call.
    conn.executescript(AUDIT_SCHEMA)
    conn.commit()
    return conn


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(AUDIT_SCHEMA)
    conn.commit()
    conn.close()


def log_audit(actor: str, action: str, target: str, detail: dict) -> None:
    conn = _connect()
    conn.execute(
        "INSERT INTO audit_log (ts, actor, action, target, detail) VALUES (?, ?, ?, ?, ?)",
        (time.time(), actor, action, target, json.dumps(detail, sort_keys=True)),
    )
    conn.commit()
    conn.close()


def record_run(app: str, outcome: str, session_id: str = "") -> None:
    conn = _connect()
    conn.execute(
        "INSERT INTO runs (ts, app, outcome, session_id) VALUES (?, ?, ?, ?)",
        (time.time(), app, outcome, session_id),
    )
    conn.commit()
    conn.close()


def list_audit(limit: int = 100) -> list[dict]:
    conn = _connect()
    rows = conn.execute("SELECT * FROM audit_log ORDER BY seq DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def run_counts() -> dict:
    """The evidence denominator: outcomes out of total runs."""
    conn = _connect()
    rows = conn.execute("SELECT outcome, COUNT(*) AS n FROM runs GROUP BY outcome").fetchall()
    conn.close()
    counts = {r["outcome"]: r["n"] for r in rows}
    total = sum(counts.values())
    return {"total": total, **counts}
