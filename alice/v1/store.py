"""Memory store on SQLite: sessions, messages, entities, memories, links. Nothing is hard-deleted."""

import json
import logging
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from ..common.clock import Clock, iso
from ..common.db import get_meta, set_meta
from ..common.text import name_matches, words
from ..common.trace import Tracer

log = logging.getLogger(__name__)

SCHEMA_VERSION = "1"

MEMORY_SCHEMA = """
-- Graph nodes: people, pets, places, topics. USER — the user; SELF — the agent itself.
CREATE TABLE IF NOT EXISTS entities (
    id         INTEGER PRIMARY KEY,
    key        TEXT NOT NULL UNIQUE,         -- lower(name)
    name       TEXT NOT NULL,
    type       TEXT NOT NULL DEFAULT 'thing',
    aliases    TEXT NOT NULL DEFAULT '[]',   -- JSON list
    created_at TEXT NOT NULL
);

-- Memory units.
--   kind: fact | episode
--   tier: core (always in the prompt) | normal (retrieved by relevance)
-- Current memory: valid_to IS NULL. Outdated records stay — history is kept.
CREATE TABLE IF NOT EXISTS memories (
    id             INTEGER PRIMARY KEY,
    kind           TEXT NOT NULL,
    tier           TEXT NOT NULL DEFAULT 'normal',
    content        TEXT NOT NULL,
    importance     REAL NOT NULL DEFAULT 0.5,
    embedding      BLOB,
    valid_from     TEXT NOT NULL,
    valid_to       TEXT,
    superseded_by  INTEGER REFERENCES memories(id),
    source_session INTEGER,
    created_at     TEXT NOT NULL,
    last_accessed  TEXT,
    access_count   INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS memories_active ON memories(valid_to, tier);
CREATE INDEX IF NOT EXISTS memories_time ON memories(valid_from);

CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
    USING fts5(content, content='memories', content_rowid='id');

CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content);
END;
CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content) VALUES ('delete', old.id, old.content);
END;
CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE OF content ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content) VALUES ('delete', old.id, old.content);
    INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content);
END;

CREATE TABLE IF NOT EXISTS memory_entities (
    memory_id INTEGER NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    PRIMARY KEY (memory_id, entity_id)
);
CREATE INDEX IF NOT EXISTS memory_entities_e ON memory_entities(entity_id);

CREATE TABLE IF NOT EXISTS entity_links (
    src      INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    dst      INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    relation TEXT NOT NULL,              -- "sister of", "works at"
    PRIMARY KEY (src, dst, relation)
);

CREATE TABLE IF NOT EXISTS memory_links (
    src      INTEGER NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    dst      INTEGER NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    relation TEXT NOT NULL,              -- contains (episode -> fact) | led_to (src is a cause of dst)
    PRIMARY KEY (src, dst, relation)
);
"""

USER = "USER"
SELF = "SELF"
USER_ALIASES = {"user", "the user", "собеседник", "пользователь"}
SELF_ALIASES = {"self", "alice", "алиса", "assistant", "ассистент"}

DUPLICATE_SIMILARITY = 0.95

Embedder = Callable[[list[str]], np.ndarray]


@dataclass
class Memory:
    id: int
    kind: str
    tier: str
    content: str
    importance: float
    valid_from: str
    created_at: str
    access_count: int = 0
    last_accessed: str | None = None
    valid_to: str | None = None
    superseded_by: int | None = None
    source_session: int | None = None


@dataclass
class Entity:
    id: int
    key: str
    name: str
    type: str
    aliases: list[str]


def _memory(row) -> Memory:
    return Memory(row["id"], row["kind"], row["tier"], row["content"], row["importance"], row["valid_from"],
                  row["created_at"], row["access_count"], row["last_accessed"], row["valid_to"],
                  row["superseded_by"], row["source_session"])


def _entity(row) -> Entity:
    return Entity(row["id"], row["key"], row["name"], row["type"], json.loads(row["aliases"]))


class MemoryStore:
    def __init__(self, db: sqlite3.Connection, clock: Clock, embed: Embedder | None = None,
                 tracer: Tracer | None = None):
        self.db, self.clock, self.embed = db, clock, embed
        self.tracer = tracer or Tracer(db, clock)
        db.executescript(MEMORY_SCHEMA)
        if get_meta(db, "schema_version") is None:
            set_meta(db, "schema_version", SCHEMA_VERSION)
        self._vec_cache: tuple[str | None, list[int], np.ndarray | None] = (None, [], None)
        self._ent_cache: tuple[str | None, list[Entity]] = (None, [])
        self.user_id = self.upsert_entity(USER, "person")
        self.self_id = self.upsert_entity(SELF, "self")

    def now(self) -> str:
        return iso(self.clock.now())

    def _event(self, op: str, memory_id: int | None, **detail) -> None:
        self.tracer.memory_event(op, memory_id, detail)

    # ---------- data version (cache invalidation) ----------

    def version(self) -> str:
        return get_meta(self.db, "version", "0")

    def _bump(self) -> None:
        self.db.execute("INSERT INTO meta(key, value) VALUES('version', '1') "
                        "ON CONFLICT(key) DO UPDATE SET value = CAST(value AS INTEGER) + 1")

    # ---------- sessions and messages ----------

    def start_session(self) -> int:
        return self.db.execute("INSERT INTO sessions(started_at) VALUES (?)", (self.now(),)).lastrowid

    def session_info(self, session_id: int):
        return self.db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()

    def open_sessions(self) -> list[int]:
        return [r[0] for r in self.db.execute("SELECT id FROM sessions WHERE ended_at IS NULL ORDER BY id")]

    def set_session_summary(self, session_id: int, summary: str) -> None:
        self.db.execute("UPDATE sessions SET summary=? WHERE id=?", (summary, session_id))

    def end_session(self, session_id: int, summary: str | None) -> None:
        last = self.last_message(session_id)
        self.db.execute("UPDATE sessions SET ended_at=?, summary=COALESCE(?, summary) WHERE id=?",
                        (last["ts"] if last else self.now(), summary, session_id))

    def delete_session(self, session_id: int) -> None:
        self.db.execute("DELETE FROM sessions WHERE id=?", (session_id,))

    def add_message(self, session_id: int, role: str, content: str, context_ids=()) -> int:
        return self.db.execute(
            "INSERT INTO messages(session_id, role, content, ts, context_ids) VALUES (?, ?, ?, ?, ?)",
            (session_id, role, content, self.now(), json.dumps(list(context_ids)))).lastrowid

    def last_message(self, session_id: int):
        return self.db.execute("SELECT * FROM messages WHERE session_id=? ORDER BY id DESC LIMIT 1",
                               (session_id,)).fetchone()

    def session_messages(self, session_id: int, from_id: int = 0) -> list:
        return self.db.execute("SELECT * FROM messages WHERE session_id=? AND id >= ? ORDER BY id",
                               (session_id, from_id)).fetchall()

    def message_count(self, session_id: int) -> int:
        return self.db.execute("SELECT COUNT(*) FROM messages WHERE session_id=?", (session_id,)).fetchone()[0]

    def unprocessed_messages(self, session_id: int) -> list:
        return self.db.execute("SELECT * FROM messages WHERE session_id=? AND processed=0 ORDER BY id",
                               (session_id,)).fetchall()

    def mark_processed(self, message_ids: list[int]) -> None:
        self.db.executemany("UPDATE messages SET processed=1 WHERE id=?", [(i,) for i in message_ids])

    def previous_session(self, before_id: int):
        """The last session before this one that had any user messages."""
        return self.db.execute(
            """SELECT s.*, (SELECT MAX(ts) FROM messages WHERE session_id=s.id) AS last_ts
               FROM sessions s WHERE s.id < ?
               AND EXISTS (SELECT 1 FROM messages WHERE session_id=s.id AND role='user')
               ORDER BY s.id DESC LIMIT 1""", (before_id,)).fetchone()

    def acquaintance(self) -> tuple[str | None, int]:
        """(first user message ts, number of sessions with user messages)."""
        first = self.db.execute("SELECT MIN(ts) FROM messages WHERE role='user'").fetchone()[0]
        count = self.db.execute("SELECT COUNT(DISTINCT session_id) FROM messages WHERE role='user'").fetchone()[0]
        return first, count

    # ---------- entities ----------

    def entities(self) -> list[Entity]:
        version = self.version()
        if self._ent_cache[0] != version:
            self._ent_cache = (version, [_entity(r) for r in self.db.execute("SELECT * FROM entities ORDER BY id")])
        return self._ent_cache[1]

    def find_entity(self, name: str) -> Entity | None:
        key = name.strip().lower()
        if key in USER_ALIASES:
            key = USER.lower()
        elif key in SELF_ALIASES:
            key = SELF.lower()
        for e in self.entities():
            if e.key == key or e.name.lower() == key or key in (a.lower() for a in e.aliases):
                return e
        return None

    def upsert_entity(self, name: str, type: str | None = None, aliases=()) -> int:
        name = name.strip()
        existing = self.find_entity(name)
        if existing:
            new_aliases = sorted(set(existing.aliases) | {a.strip() for a in aliases
                                                          if a.strip() and a.strip().lower() != existing.name.lower()})
            new_type = type if type and existing.type == "thing" else existing.type
            if new_aliases != sorted(existing.aliases) or new_type != existing.type:
                self.db.execute("UPDATE entities SET aliases=?, type=? WHERE id=?",
                                (json.dumps(new_aliases, ensure_ascii=False), new_type, existing.id))
                self._bump()
            return existing.id
        entity_id = self.db.execute(
            "INSERT INTO entities(key, name, type, aliases, created_at) VALUES (?, ?, ?, ?, ?)",
            (name.lower(), name, type or "thing",
             json.dumps([a.strip() for a in aliases if a.strip()], ensure_ascii=False), self.now())).lastrowid
        self._bump()
        return entity_id

    def entity_label(self, entity_id: int) -> str:
        """USER/SELF rendered for prompts: "the user (Mikhail)", "Alice (you)"."""
        e = next((e for e in self.entities() if e.id == entity_id), None)
        if e is None:
            return "?"
        if e.id == self.user_id:
            return f"the user ({', '.join(e.aliases)})" if e.aliases else "the user"
        if e.id == self.self_id:
            return "Alice (you)"
        return e.name

    def user_name(self) -> str | None:
        e = next((e for e in self.entities() if e.id == self.user_id), None)
        return e.aliases[0] if e and e.aliases else None

    def entities_in_text(self, text: str) -> list[Entity]:
        text_words = words(text)
        return [e for e in self.entities()
                if e.id not in (self.user_id, self.self_id)
                and any(name_matches(n, text_words) for n in [e.name, *e.aliases])]

    def link_entities(self, src: str, relation: str, dst: str) -> None:
        a, b = self.upsert_entity(src), self.upsert_entity(dst)
        if a != b and relation.strip():
            self.db.execute("INSERT OR IGNORE INTO entity_links(src, dst, relation) VALUES (?, ?, ?)",
                            (a, b, relation.strip()))

    def entity_relations(self, entity_ids) -> list[tuple[int, str, int]]:
        ids = list(entity_ids)
        if not ids:
            return []
        q = ",".join("?" * len(ids))
        return [(r[0], r[1], r[2]) for r in self.db.execute(
            f"SELECT src, relation, dst FROM entity_links WHERE src IN ({q}) OR dst IN ({q})", [*ids, *ids])]

    # ---------- memories ----------

    def embed_one(self, text: str) -> np.ndarray | None:
        if not self.embed or not text.strip():
            return None
        try:
            return self.embed([text])[0]
        except Exception as e:  # network/limits: carry on without vectors, backfill later
            log.warning("embedding failed: %s", e)
            return None

    def add_memory(self, content: str, *, kind: str = "fact", tier: str = "normal", importance: float = 0.5,
                   entities=(), valid_from: str | None = None, source_session: int | None = None) -> int:
        content = content.strip()
        try:
            importance = max(0.0, min(1.0, float(importance)))
        except (TypeError, ValueError):
            importance = 0.5
        vec = self.embed_one(content)
        if vec is not None and (dup := self._find_duplicate(vec)) is not None:
            dup_id, similarity = dup
            self._link_memory_entities(dup_id, entities)
            if tier == "core":
                self.db.execute("UPDATE memories SET tier='core' WHERE id=?", (dup_id,))
                self._bump()
            self._event("dedup", dup_id, content=content, similarity=round(similarity, 4), tier=tier)
            return dup_id
        now = self.now()
        memory_id = self.db.execute(
            """INSERT INTO memories(kind, tier, content, importance, embedding, valid_from, source_session, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (kind, tier, content, importance, vec.tobytes() if vec is not None else None,
             valid_from or now, source_session, now)).lastrowid
        names = self._link_memory_entities(memory_id, entities)
        self._bump()
        self._event("add", memory_id, kind=kind, tier=tier, importance=importance, content=content, entities=names)
        return memory_id

    def _link_memory_entities(self, memory_id: int, entity_names) -> list[str]:
        linked = []
        for name in entity_names:
            if isinstance(name, str) and name.strip():
                self.db.execute("INSERT OR IGNORE INTO memory_entities VALUES (?, ?)",
                                (memory_id, self.upsert_entity(name)))
                linked.append(name.strip())
        return linked

    def _find_duplicate(self, vec: np.ndarray) -> tuple[int, float] | None:
        ids, mat = self._vectors()
        if not ids:
            return None
        sims = mat @ vec
        i = int(np.argmax(sims))
        return (ids[i], float(sims[i])) if sims[i] >= DUPLICATE_SIMILARITY else None

    def link_memories(self, src: int, dst: int, relation: str) -> None:
        if src != dst:
            cur = self.db.execute("INSERT OR IGNORE INTO memory_links VALUES (?, ?, ?)", (src, dst, relation))
            if cur.rowcount:
                self._event("link", dst, src=src, dst=dst, relation=relation)

    def supersede(self, old_id: int, new_id: int) -> None:
        """The fact is outdated (moved, changed jobs…): close it, don't delete it."""
        cur = self.db.execute("UPDATE memories SET valid_to=?, superseded_by=? WHERE id=? AND valid_to IS NULL",
                              (self.now(), new_id, old_id))
        if cur.rowcount:
            self._bump()
            self._event("supersede", old_id, superseded_by=new_id)

    def forget(self, memory_id: int) -> bool:
        cur = self.db.execute("UPDATE memories SET valid_to=? WHERE id=? AND valid_to IS NULL",
                              (self.now(), memory_id))
        if cur.rowcount:
            self._bump()
            self._event("forget", memory_id)
        return cur.rowcount > 0

    def touch(self, memory_ids) -> None:
        """Rehearsal: being shown in a prompt refreshes a memory."""
        now = self.now()
        for i in memory_ids:
            self.db.execute("UPDATE memories SET last_accessed=?, access_count=access_count+1 WHERE id=?", (now, i))
            self._event("touch", i)

    def causes(self, memory_id: int, depth: int = 2) -> list[Memory]:
        """What a memory grew out of: the led_to chain backwards, nearest first."""
        chain, frontier, seen = [], [memory_id], {memory_id}
        for _ in range(depth):
            if not frontier:
                break
            q = ",".join("?" * len(frontier))
            srcs = [r[0] for r in self.db.execute(
                f"SELECT src FROM memory_links WHERE relation='led_to' AND dst IN ({q})", frontier) if r[0] not in seen]
            seen.update(srcs)
            found = self.memories_by_ids(srcs)
            chain.extend(sorted(found.values(), key=lambda m: m.valid_from, reverse=True))
            frontier = list(found)
        return chain

    def causal_out_degree(self, ids) -> dict[int, int]:
        ids = list(ids)
        if not ids:
            return {}
        q = ",".join("?" * len(ids))
        return {r[0]: r[1] for r in self.db.execute(
            f"SELECT src, COUNT(*) FROM memory_links WHERE relation='led_to' AND src IN ({q}) GROUP BY src", ids)}

    def links_of(self, ids) -> list[tuple[int, int, str]]:
        ids = list(ids)
        if not ids:
            return []
        q = ",".join("?" * len(ids))
        return [(r[0], r[1], r[2]) for r in self.db.execute(
            f"SELECT src, dst, relation FROM memory_links WHERE src IN ({q}) OR dst IN ({q})", [*ids, *ids])]

    def recent_memories(self, limit: int = 8) -> list[Memory]:
        rows = self.db.execute("SELECT * FROM memories WHERE valid_to IS NULL AND tier != 'core' "
                               "ORDER BY id DESC LIMIT ?", (limit,))
        return [_memory(r) for r in rows]

    def recent_episodes(self, limit: int = 6) -> list[Memory]:
        rows = self.db.execute("SELECT * FROM memories WHERE kind='episode' AND valid_to IS NULL "
                               "ORDER BY valid_from DESC LIMIT ?", (limit,))
        return [_memory(r) for r in rows]

    def core_memories(self) -> list[Memory]:
        rows = self.db.execute("SELECT * FROM memories WHERE tier='core' AND valid_to IS NULL "
                               "ORDER BY importance DESC, id")
        return [_memory(r) for r in rows]

    def memories_by_ids(self, ids, *, active_only: bool = True) -> dict[int, Memory]:
        ids = list(ids)
        if not ids:
            return {}
        q = ",".join("?" * len(ids))
        active = " AND valid_to IS NULL" if active_only else ""
        return {r["id"]: _memory(r) for r in self.db.execute(f"SELECT * FROM memories WHERE id IN ({q}){active}", ids)}

    def all_memories(self, *, active_only: bool = True) -> list[Memory]:
        where = "WHERE valid_to IS NULL" if active_only else ""
        return [_memory(r) for r in self.db.execute(f"SELECT * FROM memories {where} ORDER BY id")]

    def memory_entity_ids(self, memory_ids) -> list[int]:
        ids = list(memory_ids)
        if not ids:
            return []
        q = ",".join("?" * len(ids))
        return [r[0] for r in self.db.execute(
            f"SELECT DISTINCT entity_id FROM memory_entities WHERE memory_id IN ({q})", ids)]

    def memories_of_entities(self, entity_ids) -> list[int]:
        ids = list(entity_ids)
        if not ids:
            return []
        q = ",".join("?" * len(ids))
        return [r[0] for r in self.db.execute(f"SELECT memory_id FROM memory_entities WHERE entity_id IN ({q})", ids)]

    def memories_in_range(self, start: str, end: str) -> list[tuple[int, str]]:
        return [(r[0], r[1]) for r in self.db.execute(
            "SELECT id, kind FROM memories WHERE valid_from BETWEEN ? AND ?", (start, end))]

    def fts(self, query: str, limit: int = 30) -> list[int]:
        try:
            return [r[0] for r in self.db.execute(
                "SELECT rowid FROM memories_fts WHERE memories_fts MATCH ? ORDER BY rank LIMIT ?", (query, limit))]
        except sqlite3.OperationalError as e:
            log.warning("fts query failed (%s): %s", query, e)
            return []

    def session_memory_ids(self, session_id: int, kind: str = "fact") -> list[int]:
        return [r[0] for r in self.db.execute(
            "SELECT id FROM memories WHERE source_session=? AND kind=? AND valid_to IS NULL", (session_id, kind))]

    def backfill_embeddings(self) -> int:
        """Compute vectors for records saved without them (e.g. after a network failure)."""
        if not self.embed:
            return 0
        rows = self.db.execute("SELECT id, content FROM memories WHERE embedding IS NULL").fetchall()
        for i in range(0, len(rows), 64):
            batch = rows[i:i + 64]
            vecs = self.embed([r["content"] for r in batch])
            self.db.executemany("UPDATE memories SET embedding=? WHERE id=?",
                                [(v.tobytes(), r["id"]) for v, r in zip(vecs, batch)])
        if rows:
            self._bump()
        return len(rows)

    def vectors(self) -> tuple[list[int], np.ndarray | None]:
        return self._vectors()

    def _vectors(self) -> tuple[list[int], np.ndarray | None]:
        """Matrix of active memory vectors. Brute force: fine up to tens of thousands of records."""
        version = self.version()
        if self._vec_cache[0] != version:
            rows = self.db.execute("SELECT id, embedding FROM memories "
                                   "WHERE valid_to IS NULL AND embedding IS NOT NULL").fetchall()
            ids = [r[0] for r in rows]
            mat = np.stack([np.frombuffer(r[1], dtype=np.float32) for r in rows]) if rows else None
            self._vec_cache = (version, ids, mat)
        return self._vec_cache[1], self._vec_cache[2]
