"""AppealMate — persistence. SQLite + append-only audit log + run counts + sessions."""
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path


def _db_path() -> Path:
    """Where the database lives.

    Serverless hosts (Vercel, Lambda) mount the project read-only, so a database
    beside the source cannot be written. /tmp is writable there but is
    per-instance and ephemeral — fine for a demo, not for durability. Locally we
    keep the file next to the source so state survives a restart.
    """
    if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return Path("/tmp/appealmate.db")
    return Path(__file__).parent / "appealmate.db"


DB_PATH = _db_path()

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
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    updated REAL NOT NULL,
    payload TEXT NOT NULL
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


# --- session persistence -------------------------------------------------
# Serverless invocations do not share memory, so an in-memory session dict
# loses the conversation between requests. Sessions are stored as JSON.

def save_session(session_id: str, payload: dict) -> None:
    conn = _connect()
    conn.execute(
        "INSERT OR REPLACE INTO sessions (session_id, updated, payload) VALUES (?, ?, ?)",
        (session_id, time.time(), json.dumps(payload)),
    )
    conn.commit()
    conn.close()


def load_session(session_id: str) -> dict | None:
    conn = _connect()
    row = conn.execute(
        "SELECT payload FROM sessions WHERE session_id = ?", (session_id,)
    ).fetchone()
    conn.close()
    return json.loads(row["payload"]) if row else None
