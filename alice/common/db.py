"""SQLite connection and the conversation tables every agent (V1 and baselines) shares."""

import sqlite3
from pathlib import Path

CORE_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    id         INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL,
    ended_at   TEXT,
    summary    TEXT             -- rolling summary, then the final one
);

-- Raw log. Never goes into the prompt wholesale (except in the B1 baseline).
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY,
    session_id  INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    ts          TEXT NOT NULL,
    processed   INTEGER NOT NULL DEFAULT 0,     -- passed through the extractor
    context_ids TEXT NOT NULL DEFAULT '[]'      -- memory ids shown when this reply was written
);
CREATE INDEX IF NOT EXISTS messages_session ON messages(session_id, id);
"""


def connect(path: Path | str) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30, check_same_thread=False, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript(CORE_SCHEMA)
    return db


def get_meta(db: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    row = db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def set_meta(db: sqlite3.Connection, key: str, value) -> None:
    db.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", (key, str(value)))


def backup(db: sqlite3.Connection, path: Path | str) -> None:
    """Consistent copy of a live database (used for probe forks)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    dst = sqlite3.connect(path)
    try:
        db.backup(dst)
    finally:
        dst.close()
