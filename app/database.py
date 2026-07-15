"""
SQLite storage for the voice interview agent.

Three tables:
  contacts  – the people to call (uploaded from your CSV/Excel)
  calls     – one row per phone call attempt (status, recording, summary)
  messages  – the transcript: each thing the AI or the person said

Uses the standard-library `sqlite3` so the dashboard runs with almost no
dependencies. No ORM needed for a project this size.
"""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from app import config


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def get_conn():
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create tables if they don't exist. Safe to call every startup."""
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS contacts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT,
                phone       TEXT NOT NULL,
                language    TEXT,
                notes       TEXT,
                created_at  TEXT
            );

            CREATE TABLE IF NOT EXISTS calls (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_id    INTEGER,
                name          TEXT,
                phone         TEXT NOT NULL,
                status        TEXT DEFAULT 'pending',   -- pending|in_progress|completed|failed
                language      TEXT,
                note          TEXT,                     -- the question to ask (from the Excel 'notes' column)
                recording_url TEXT,
                summary       TEXT,
                started_at    TEXT,
                ended_at      TEXT,
                created_at    TEXT,
                FOREIGN KEY (contact_id) REFERENCES contacts(id)
            );

            CREATE TABLE IF NOT EXISTS messages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                call_id    INTEGER NOT NULL,
                role       TEXT NOT NULL,              -- 'agent' or 'user'
                content    TEXT NOT NULL,
                created_at TEXT,
                FOREIGN KEY (call_id) REFERENCES calls(id)
            );
            """
        )
        # Migration: add 'note' to calls if an older database is missing it.
        existing = [r[1] for r in conn.execute("PRAGMA table_info(calls)")]
        if "note" not in existing:
            conn.execute("ALTER TABLE calls ADD COLUMN note TEXT")

        # Key/value settings — used to store the global interview question(s).
        conn.execute(
            "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)"
        )


# ------------------------------- contacts ----------------------------------
def add_contact(name, phone, language=None, notes=None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO contacts (name, phone, language, notes, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, phone, language, notes, _now()),
        )
        return cur.lastrowid


def list_contacts():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM contacts ORDER BY id DESC"
        )]


# -------------------------------- calls ------------------------------------
def create_call(phone, name=None, contact_id=None, language=None, note=None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO calls (contact_id, name, phone, status, language, note, "
            "started_at, created_at) VALUES (?, ?, ?, 'in_progress', ?, ?, ?, ?)",
            (contact_id, name, phone, language, note, _now(), _now()),
        )
        return cur.lastrowid


def finish_call(call_id, status="completed", recording_url=None, summary=None):
    with get_conn() as conn:
        conn.execute(
            "UPDATE calls SET status=?, ended_at=?, recording_url=COALESCE(?, recording_url), "
            "summary=COALESCE(?, summary) WHERE id=?",
            (status, _now(), recording_url, summary, call_id),
        )


def set_summary(call_id, summary):
    with get_conn() as conn:
        conn.execute("UPDATE calls SET summary=? WHERE id=?", (summary, call_id))


def list_calls():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM calls ORDER BY id DESC"
        )]


def get_call(call_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM calls WHERE id=?", (call_id,)).fetchone()
        return dict(row) if row else None


# ------------------------------ messages -----------------------------------
def add_message(call_id, role, content):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (call_id, role, content, created_at) "
            "VALUES (?, ?, ?, ?)",
            (call_id, role, content, _now()),
        )


def get_messages(call_id):
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM messages WHERE call_id=? ORDER BY id", (call_id,)
        )]


# ------------------------------ settings -----------------------------------
def get_setting(key, default=None):
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row and row["value"] is not None else default


def set_setting(key, value):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def get_transcript_text(call_id) -> str:
    """The full conversation as plain text, used for AI summarization."""
    lines = []
    for m in get_messages(call_id):
        who = "Interviewer" if m["role"] == "agent" else "Person"
        lines.append(f"{who}: {m['content']}")
    return "\n".join(lines)


if __name__ == "__main__":
    init_db()
    print(f"Database ready at {config.DB_PATH}")
