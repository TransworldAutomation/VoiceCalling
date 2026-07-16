"""
Storage for the voice interview agent.

Works two ways, chosen automatically:

  * If the env var DATABASE_URL is set (e.g. a Supabase Postgres URL), all data
    is stored in that hosted Postgres database. This is what you want in the
    cloud (Render), because it SURVIVES restarts — your contacts, call log and
    saved question are never wiped.

  * Otherwise it falls back to a local SQLite file (data/interviews.db), which
    needs no setup and is perfect for running on your own machine.

Three tables either way:
  contacts  – the people to call (uploaded from your CSV/Excel)
  calls     – one row per phone call attempt (status, recording, summary)
  messages  – the transcript: each thing the AI or the person said
  settings  – key/value store for the global interview question + language
"""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from app import config

# When DATABASE_URL is present we talk to Postgres (Supabase); otherwise SQLite.
DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip()
USE_PG = bool(DATABASE_URL)

# Human-readable status of the storage backend, surfaced on the dashboard so you
# can SEE whether your data is being saved permanently or only temporarily:
#   "postgres"        -> connected to Supabase; data is permanent
#   "sqlite"          -> local SQLite (no DATABASE_URL set); fine on your PC
#   "sqlite-fallback" -> DATABASE_URL set but the connection FAILED; using
#                        temporary storage, data will be lost. Fix DATABASE_URL.
DB_STATUS = "sqlite"
DB_ERROR = ""  # last connection error message, for the fallback case

if USE_PG:
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as e:  # driver not installed — degrade instead of crashing
        USE_PG = False
        DB_STATUS = "sqlite-fallback"
        DB_ERROR = f"psycopg driver not installed: {e}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ph(sql: str) -> str:
    """SQLite uses '?' placeholders; Postgres uses '%s'. We write every query with
    '?' and translate here so the rest of the file stays database-agnostic."""
    return sql.replace("?", "%s") if USE_PG else sql


@contextmanager
def get_conn():
    if USE_PG:
        conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    else:
        os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def _exec(conn, sql, params=()):
    """Run a query with the right placeholder style; returns the cursor."""
    return conn.execute(_ph(sql), params)


def _insert(conn, sql, params):
    """INSERT and return the new row's id, for both databases."""
    if USE_PG:
        cur = conn.execute(_ph(sql + " RETURNING id"), params)
        return cur.fetchone()["id"]
    cur = conn.execute(sql, params)
    return cur.lastrowid


def _create_tables():
    """Run the CREATE TABLE statements against whichever backend is active."""
    # 'id' auto-increment differs between the two engines.
    pk = "BIGSERIAL PRIMARY KEY" if USE_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"

    statements = [
        f"""CREATE TABLE IF NOT EXISTS contacts (
                id          {pk},
                name        TEXT,
                phone       TEXT NOT NULL,
                language    TEXT,
                notes       TEXT,
                created_at  TEXT
            )""",
        f"""CREATE TABLE IF NOT EXISTS calls (
                id            {pk},
                contact_id    INTEGER,
                name          TEXT,
                phone         TEXT NOT NULL,
                status        TEXT DEFAULT 'pending',
                language      TEXT,
                note          TEXT,
                recording_url TEXT,
                summary       TEXT,
                started_at    TEXT,
                ended_at      TEXT,
                created_at    TEXT
            )""",
        f"""CREATE TABLE IF NOT EXISTS messages (
                id         {pk},
                call_id    INTEGER NOT NULL,
                role       TEXT NOT NULL,
                content    TEXT NOT NULL,
                created_at TEXT
            )""",
        "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)",
    ]

    with get_conn() as conn:
        for s in statements:
            conn.execute(s)
        # Migration for OLD local SQLite databases missing the 'note' column.
        if not USE_PG:
            existing = [r[1] for r in conn.execute("PRAGMA table_info(calls)")]
            if "note" not in existing:
                conn.execute("ALTER TABLE calls ADD COLUMN note TEXT")


def init_db():
    """Create tables if they don't exist. Safe to call every startup.

    Never crashes the app: if DATABASE_URL is set but Supabase can't be reached
    (wrong password, wrong host, etc.), we log a loud warning, fall back to the
    temporary SQLite file so the site still runs, and record DB_STATUS so the
    dashboard can warn you that data is NOT being saved permanently.
    """
    global USE_PG, DB_STATUS, DB_ERROR

    if USE_PG:
        try:
            _create_tables()
            DB_STATUS = "postgres"
            host = DATABASE_URL.split("@")[-1].split("/")[0] if "@" in DATABASE_URL else "?"
            print(f"[database] Using Postgres (Supabase) -> {host}", flush=True)
            return
        except Exception as e:
            # Connection/setup failed — degrade gracefully to SQLite.
            USE_PG = False
            DB_STATUS = "sqlite-fallback"
            DB_ERROR = str(e).splitlines()[0][:300] if str(e) else e.__class__.__name__
            print(
                "[database] ERROR: DATABASE_URL is set but the connection FAILED "
                f"-> {DB_ERROR}\n[database] Falling back to TEMPORARY SQLite. Your "
                "data will NOT persist. Check the DATABASE_URL value in Render.",
                flush=True,
            )

    _create_tables()
    if DB_STATUS != "sqlite-fallback":
        DB_STATUS = "sqlite"
        print(
            "[database] Using local SQLite (DATABASE_URL not set) -> "
            f"{config.DB_PATH}. Data will NOT persist across restarts on Render.",
            flush=True,
        )


# ------------------------------- contacts ----------------------------------
def add_contact(name, phone, language=None, notes=None) -> int:
    with get_conn() as conn:
        return _insert(
            conn,
            "INSERT INTO contacts (name, phone, language, notes, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, phone, language, notes, _now()),
        )


def list_contacts():
    with get_conn() as conn:
        return [dict(r) for r in _exec(
            conn, "SELECT * FROM contacts ORDER BY id DESC"
        )]


# -------------------------------- calls ------------------------------------
def create_call(phone, name=None, contact_id=None, language=None, note=None) -> int:
    with get_conn() as conn:
        return _insert(
            conn,
            "INSERT INTO calls (contact_id, name, phone, status, language, note, "
            "started_at, created_at) VALUES (?, ?, ?, 'in_progress', ?, ?, ?, ?)",
            (contact_id, name, phone, language, note, _now(), _now()),
        )


def finish_call(call_id, status="completed", recording_url=None, summary=None):
    with get_conn() as conn:
        _exec(
            conn,
            "UPDATE calls SET status=?, ended_at=?, recording_url=COALESCE(?, recording_url), "
            "summary=COALESCE(?, summary) WHERE id=?",
            (status, _now(), recording_url, summary, call_id),
        )


def set_summary(call_id, summary):
    with get_conn() as conn:
        _exec(conn, "UPDATE calls SET summary=? WHERE id=?", (summary, call_id))


def list_calls():
    with get_conn() as conn:
        return [dict(r) for r in _exec(
            conn, "SELECT * FROM calls ORDER BY id DESC"
        )]


def get_call(call_id):
    with get_conn() as conn:
        row = _exec(conn, "SELECT * FROM calls WHERE id=?", (call_id,)).fetchone()
        return dict(row) if row else None


# ------------------------------ messages -----------------------------------
def add_message(call_id, role, content):
    with get_conn() as conn:
        _exec(
            conn,
            "INSERT INTO messages (call_id, role, content, created_at) "
            "VALUES (?, ?, ?, ?)",
            (call_id, role, content, _now()),
        )


def get_messages(call_id):
    with get_conn() as conn:
        return [dict(r) for r in _exec(
            conn, "SELECT * FROM messages WHERE call_id=? ORDER BY id", (call_id,)
        )]


# ------------------------------ settings -----------------------------------
def get_setting(key, default=None):
    with get_conn() as conn:
        row = _exec(conn, "SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row and row["value"] is not None else default


def set_setting(key, value):
    with get_conn() as conn:
        _exec(
            conn,
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def storage_status() -> dict:
    """Where data is being stored right now — used for the dashboard banner."""
    return {"backend": DB_STATUS, "error": DB_ERROR, "permanent": DB_STATUS == "postgres"}


def get_transcript_text(call_id) -> str:
    """The full conversation as plain text, used for AI summarization."""
    lines = []
    for m in get_messages(call_id):
        who = "Interviewer" if m["role"] == "agent" else "Person"
        lines.append(f"{who}: {m['content']}")
    return "\n".join(lines)


if __name__ == "__main__":
    init_db()
    where = "Postgres (DATABASE_URL)" if USE_PG else config.DB_PATH
    print(f"Database ready -> {where}")
