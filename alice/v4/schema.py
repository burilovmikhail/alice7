"""V4 tables, next to V1's, V2's and V3's in the same SQLite file. Times are sim-clock ISO strings.

The field's numbers (activations, base-level uses, edges, noise and generator state, drives, attention, gate) live
as one snapshot in v4_state, rewritten at every event boundary, so a fork made with snapshot() starts from exactly
the state the original had (D11). Node descriptions live in v4_nodes; everything else is a log."""

import sqlite3

V4_SCHEMA_VERSION = "1"

V4_SCHEMA = """
CREATE TABLE IF NOT EXISTS v4_nodes (
    id         INTEGER PRIMARY KEY,
    kind       TEXT NOT NULL,       -- memory|episode|thought|dream|intention|question|trace|user|self
    ref_id     INTEGER,             -- the row in the table it stands for (memories, thoughts, intentions_v3, ...)
    label      TEXT NOT NULL DEFAULT '',
    source     TEXT NOT NULL DEFAULT 'external',   -- external|own
    created_at TEXT NOT NULL,
    embedding  BLOB
);
CREATE INDEX IF NOT EXISTS v4_nodes_ref ON v4_nodes(kind, ref_id);

CREATE TABLE IF NOT EXISTS v4_state (
    key   TEXT PRIMARY KEY,
    value BLOB
);

-- Per step: field_top, drives_log and gate_log of spec §8 in one row.
CREATE TABLE IF NOT EXISTS v4_steps (
    at        TEXT NOT NULL,
    mode      TEXT NOT NULL,        -- awake|conversation|nrem|rem
    coherence REAL NOT NULL,
    urgency   REAL NOT NULL,
    brake     REAL NOT NULL,
    focus     REAL NOT NULL,
    drives    TEXT NOT NULL,        -- {name: value}
    top       TEXT NOT NULL         -- [[node id, activation], ...]
);

-- Gate firings, dreams and near-misses, with what made them.
CREATE TABLE IF NOT EXISTS v4_firings (
    id          INTEGER PRIMARY KEY,
    at          TEXT NOT NULL,
    kind        TEXT NOT NULL,      -- fire|dream|yawn|worry
    coherence   REAL NOT NULL,
    urgency     REAL NOT NULL,
    brake       REAL NOT NULL,
    sources     TEXT NOT NULL DEFAULT '{}',
    coalition   TEXT NOT NULL DEFAULT '[]',
    cause       TEXT NOT NULL DEFAULT '',      -- due|fresh|spontaneous (fire only)
    grew_hours  REAL,                          -- how long its coalition had been growing
    wake_id     INTEGER,                       -- V3's wakes row (fire)
    thought     TEXT NOT NULL DEFAULT '',
    decisions   TEXT NOT NULL DEFAULT '[]',
    llm_call_id INTEGER
);

CREATE TABLE IF NOT EXISTS v4_attention (
    at        TEXT NOT NULL,
    event     TEXT NOT NULL,     -- switch|intrusion
    focus     REAL NOT NULL,
    energy    REAL NOT NULL,
    coalition TEXT NOT NULL
);

-- Experience traces: reply -> reaction episodes (spec §6.7). `signal` is never shown to a model.
CREATE TABLE IF NOT EXISTS v4_traces (
    id               INTEGER PRIMARY KEY,
    session_id       INTEGER,
    situation_msg_id INTEGER,
    reply_msg_id     INTEGER,
    reaction_msg_id  INTEGER,
    situation        TEXT NOT NULL,
    reply            TEXT NOT NULL,
    reaction         TEXT NOT NULL,
    kind             TEXT NOT NULL,
    what             TEXT NOT NULL DEFAULT '',
    signal           REAL NOT NULL,
    expected         REAL NOT NULL,
    pe               REAL NOT NULL,
    salience         REAL NOT NULL DEFAULT 0,
    llm_call_id      INTEGER,
    embedding        BLOB,
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS v4_learning (
    at     TEXT NOT NULL,
    event  TEXT NOT NULL,     -- pe|edges
    detail TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS v4_dissonance (
    id        INTEGER PRIMARY KEY,
    at        TEXT NOT NULL,
    belief_id INTEGER,
    belief    TEXT NOT NULL,
    weight    REAL NOT NULL,
    trace_ids TEXT NOT NULL DEFAULT '[]',
    labels    TEXT NOT NULL DEFAULT '[]',
    share     REAL NOT NULL,
    value     REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS v4_sleep (
    id     INTEGER PRIMARY KEY,
    at     TEXT NOT NULL,
    event  TEXT NOT NULL,     -- onset|nrem|rem|wake|dream|narrative|dissonance|duplicates
    detail TEXT NOT NULL DEFAULT '{}'
);

-- Episodic memory: every exchange, in order; long texts the user shared are passages (episodes.py).
CREATE TABLE IF NOT EXISTS v4_events (
    id         INTEGER PRIMARY KEY,
    session_id INTEGER,
    message_id INTEGER NOT NULL UNIQUE,   -- the user's message
    reply_id   INTEGER,
    at         TEXT NOT NULL,
    kind       TEXT NOT NULL,             -- event|passage
    seq        INTEGER NOT NULL,          -- order across all conversations
    label      TEXT NOT NULL,
    verbatim   TEXT,                      -- kept word for word (a charged passage: what struck the agent)
    valence    REAL NOT NULL DEFAULT 0,
    arousal    REAL NOT NULL DEFAULT 0
);

-- What each reply was written with, next to V2's turn_state.
CREATE TABLE IF NOT EXISTS v4_turn_state (
    message_id        INTEGER PRIMARY KEY,
    trace_ids         TEXT NOT NULL DEFAULT '[]',
    trace_activations TEXT NOT NULL DEFAULT '[]',
    wm                TEXT NOT NULL DEFAULT '[]',
    recall            TEXT NOT NULL DEFAULT '[]',
    drives            TEXT NOT NULL DEFAULT '{}',
    grip              TEXT NOT NULL DEFAULT '[]'    -- what didn't connect (grip.py)
);
"""


def ensure_schema(db: sqlite3.Connection) -> None:
    db.executescript(V4_SCHEMA)
    if "grip" not in {r[1] for r in db.execute("PRAGMA table_info(v4_turn_state)")}:   # databases from before
        db.execute("ALTER TABLE v4_turn_state ADD COLUMN grip TEXT NOT NULL DEFAULT '[]'")
    db.execute("INSERT OR IGNORE INTO meta(key, value) VALUES ('v4_schema_version', ?)", (V4_SCHEMA_VERSION,))
