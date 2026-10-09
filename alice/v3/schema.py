"""V3 tables, next to V1's and V2's in the same SQLite file. Times are sim-clock ISO strings."""

import sqlite3

V3_SCHEMA_VERSION = "1"

V3_SCHEMA = """
-- Every scheduled event in silence: what was due, whether it ran, and why not.
CREATE TABLE IF NOT EXISTS schedule_log (
    id     INTEGER PRIMARY KEY,
    at     TEXT NOT NULL,
    event  TEXT NOT NULL,        -- session_close|stream|wake|sleep
    ran    INTEGER NOT NULL,
    note   TEXT NOT NULL DEFAULT ''
);

-- The background stream: working thoughts, not memories.
CREATE TABLE IF NOT EXISTS stream_thoughts (
    id        INTEGER PRIMARY KEY,
    at        TEXT NOT NULL,
    mode      TEXT NOT NULL,     -- conversation|idle|asleep
    content   TEXT NOT NULL,
    seeds     TEXT NOT NULL DEFAULT '[]',   -- memory ids it was surfaced from
    novelty   REAL NOT NULL DEFAULT 1,
    embedding BLOB,
    consumed  INTEGER NOT NULL DEFAULT 0    -- taken up by a wake
);

-- The monitor, per check (no model).
CREATE TABLE IF NOT EXISTS pressure_log (
    id        INTEGER PRIMARY KEY,
    at        TEXT NOT NULL,
    value     REAL NOT NULL,
    threshold REAL NOT NULL,
    parts     TEXT NOT NULL DEFAULT '{}',
    woke      INTEGER NOT NULL DEFAULT 0
);

-- Expensive thought.
CREATE TABLE IF NOT EXISTS wakes (
    id          INTEGER PRIMARY KEY,
    at          TEXT NOT NULL,
    trigger     TEXT NOT NULL DEFAULT '{}',   -- pressure parts and the ids that made them
    thought     TEXT NOT NULL DEFAULT '',
    decisions   TEXT NOT NULL DEFAULT '[]',
    productive  INTEGER NOT NULL DEFAULT 0,   -- changed any persistent state
    llm_call_id INTEGER
);

CREATE TABLE IF NOT EXISTS sleep_log (
    id      INTEGER PRIMARY KEY,
    at      TEXT NOT NULL,
    phase   TEXT NOT NULL,        -- nrem|rem|lessons|portrait
    summary TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS affect_states (
    id         INTEGER PRIMARY KEY,
    at         TEXT NOT NULL,
    layer      TEXT NOT NULL,     -- fast|mood
    valence    REAL NOT NULL,
    arousal    REAL NOT NULL,
    emotions   TEXT NOT NULL DEFAULT '{}',
    cause      TEXT NOT NULL DEFAULT '',
    message_id INTEGER
);
CREATE TABLE IF NOT EXISTS memory_affect (
    memory_id INTEGER PRIMARY KEY,
    valence   REAL NOT NULL,
    arousal   REAL NOT NULL
);

-- Prospective memory with "later" (replaces V2's intentions in V3).
CREATE TABLE IF NOT EXISTS intentions_v3 (
    id                INTEGER PRIMARY KEY,
    content           TEXT NOT NULL,
    not_before        TEXT NOT NULL,       -- can't be fulfilled before this (end of the creating session)
    due               TEXT,                -- YYYY-MM-DD
    source            TEXT NOT NULL,       -- commitment|self_review|wake
    message_id        INTEGER,
    session_id        INTEGER,
    status            TEXT NOT NULL DEFAULT 'open',   -- open|done|dropped
    closed_by_message INTEGER,
    evidence          TEXT,                -- the quoted part of the answer that carried it out
    embedding         BLOB,
    created_at        TEXT NOT NULL,
    closed_at         TEXT
);

-- What the agent thought on its own (wakes, sleep insights): lasting, but weighted below lived experience.
CREATE TABLE IF NOT EXISTS thoughts (
    id        INTEGER PRIMARY KEY,
    at        TEXT NOT NULL,
    source    TEXT NOT NULL,       -- wake|sleep
    source_id INTEGER,             -- the wake or sleep_log row
    content   TEXT NOT NULL,
    embedding BLOB
);

-- Open questions the agent keeps coming back to.
CREATE TABLE IF NOT EXISTS questions (
    id              INTEGER PRIMARY KEY,
    content         TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'open',   -- open|resolved|dropped
    answer          TEXT,
    source          TEXT NOT NULL,                  -- wake|sleep
    source_id       INTEGER,
    embedding       BLOB,
    created_at      TEXT NOT NULL,
    last_considered TEXT,
    resolved_at     TEXT
);

-- Which lesson events a wake or sleep caused (V2's lesson_events stays as it is).
CREATE TABLE IF NOT EXISTS lesson_event_causes (
    event_id  INTEGER PRIMARY KEY,
    source    TEXT NOT NULL,       -- wake|sleep
    source_id INTEGER NOT NULL
);

-- Messages the agent wrote first.
CREATE TABLE IF NOT EXISTS outbox (
    message_id   INTEGER PRIMARY KEY,
    at           TEXT NOT NULL,
    wake_id      INTEGER,
    intention_id INTEGER,
    content      TEXT NOT NULL
);
"""


def ensure_schema(db: sqlite3.Connection) -> None:
    db.executescript(V3_SCHEMA)
    db.execute("INSERT OR IGNORE INTO meta(key, value) VALUES ('v3_schema_version', ?)", (V3_SCHEMA_VERSION,))
