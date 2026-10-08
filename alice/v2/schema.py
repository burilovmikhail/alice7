"""V2 tables, created next to V1's in the same SQLite file. V1 tables are not altered.
Times are sim-clock ISO strings (as in V1's memory tables); event tables also keep wall time."""

import sqlite3

V2_SCHEMA_VERSION = "1"

V2_SCHEMA = """
-- How the user reacted to a reply: the raw material of reflection.
CREATE TABLE IF NOT EXISTS feedback (
    id               INTEGER PRIMARY KEY,
    session_id       INTEGER,
    assistant_msg_id INTEGER,          -- the reply the user reacted to
    user_msg_id      INTEGER,          -- the reacting message
    signal           REAL NOT NULL,    -- -1..1
    kind             TEXT NOT NULL,    -- correction|frustration|praise|engagement|disengagement|neutral
    what             TEXT NOT NULL DEFAULT '',   -- free text: what in the reply the reaction was about
    target           TEXT,             -- classified from `what` by the judge at report time (spec D11)
    hint             TEXT NOT NULL DEFAULT '',
    explicit         INTEGER NOT NULL DEFAULT 0,
    reflected        INTEGER NOT NULL DEFAULT 0,
    llm_call_id      INTEGER,
    created_at       TEXT NOT NULL
);

-- Procedural memory: instructions to act, with a confidence that experience moves.
CREATE TABLE IF NOT EXISTS lessons (
    id                  INTEGER PRIMARY KEY,
    category            TEXT NOT NULL,         -- style|behavior|user_model|self
    rule                TEXT NOT NULL,
    situation           TEXT NOT NULL DEFAULT '',   -- '' = always
    confidence          REAL NOT NULL,
    evidence            INTEGER NOT NULL DEFAULT 1,
    status              TEXT NOT NULL DEFAULT 'active',   -- active|retired
    embedding           BLOB,
    situation_embedding BLOB,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS lessons_active ON lessons(status, confidence);

CREATE TABLE IF NOT EXISTS lesson_events (
    id           INTEGER PRIMARY KEY,
    lesson_id    INTEGER NOT NULL REFERENCES lessons(id),
    op           TEXT NOT NULL,          -- add|reinforce|weaken|revise|retire
    confidence   REAL NOT NULL,
    note         TEXT NOT NULL DEFAULT '',
    feedback_ids TEXT NOT NULL DEFAULT '[]',   -- the signals that caused it (E7 chain)
    message_id   INTEGER,                -- explicit / self lessons: the triggering message
    llm_call_id  INTEGER,
    ts           TEXT NOT NULL,
    sim_ts       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS lesson_events_lesson ON lesson_events(lesson_id, id);

-- Self-knowledge: portrait versions, the beliefs of each version, opinions on topics.
CREATE TABLE IF NOT EXISTS portraits (
    id          INTEGER PRIMARY KEY,
    content     TEXT NOT NULL,
    changes     TEXT NOT NULL DEFAULT '',
    session_id  INTEGER,
    source      TEXT NOT NULL DEFAULT 'self_review',   -- self_review|injected (E13)
    llm_call_id INTEGER,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS beliefs (
    id          INTEGER PRIMARY KEY,
    portrait_id INTEGER NOT NULL REFERENCES portraits(id),
    text        TEXT NOT NULL,
    weight      REAL NOT NULL,
    parent_id   INTEGER REFERENCES beliefs(id)    -- the same belief in the previous version
);

CREATE TABLE IF NOT EXISTS opinions (
    id            INTEGER PRIMARY KEY,
    topic         TEXT NOT NULL,
    content       TEXT NOT NULL,
    stance        REAL NOT NULL DEFAULT 0,   -- -1..1 toward the topic
    embedding     BLOB,
    session_id    INTEGER,
    source        TEXT NOT NULL DEFAULT 'self_review',   -- self_review|injected (E13)
    superseded_by INTEGER REFERENCES opinions(id),
    created_at    TEXT NOT NULL
);

-- Prospective memory.
CREATE TABLE IF NOT EXISTS intentions (
    id                INTEGER PRIMARY KEY,
    content           TEXT NOT NULL,
    due_from          TEXT,
    due_to            TEXT,
    source            TEXT NOT NULL,          -- commitment|self_review
    message_id        INTEGER,
    session_id        INTEGER,
    status            TEXT NOT NULL DEFAULT 'open',   -- open|done|dropped
    closed_by_message INTEGER,
    created_at        TEXT NOT NULL,
    closed_at         TEXT
);

-- Exactly what V2 state each reply was written with.
CREATE TABLE IF NOT EXISTS turn_state (
    message_id    INTEGER PRIMARY KEY,        -- the assistant message
    portrait_id   INTEGER,
    lesson_ids    TEXT NOT NULL DEFAULT '[]',
    opinion_ids   TEXT NOT NULL DEFAULT '[]',
    intention_ids TEXT NOT NULL DEFAULT '[]',
    switches      TEXT NOT NULL DEFAULT '{}'
);
"""

V2_TABLES = ("feedback", "lessons", "lesson_events", "portraits", "beliefs", "opinions", "intentions",
             "turn_state")


def ensure_schema(db: sqlite3.Connection) -> None:
    db.executescript(V2_SCHEMA)
    db.execute("INSERT OR IGNORE INTO meta(key, value) VALUES ('v2_schema_version', ?)", (V2_SCHEMA_VERSION,))
