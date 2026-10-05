"""Append-only instrumentation: every LLM call, retrieval and memory write.

Lives in the agent's own database (so probe forks carry it along) and is exported as JSONL per run.
"""

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from .clock import Clock, iso, wall_now

TRACE_SCHEMA = """
CREATE TABLE IF NOT EXISTS llm_calls (
    id                INTEGER PRIMARY KEY,
    ts                TEXT NOT NULL,
    sim_ts            TEXT NOT NULL,
    purpose           TEXT NOT NULL,     -- chat|extract|fold|episode|embed|judge|carryover
    model             TEXT NOT NULL,
    request           TEXT NOT NULL,     -- JSON
    response          TEXT,
    prompt_tokens     INTEGER,
    completion_tokens INTEGER,
    cost              REAL,
    latency_ms        INTEGER,
    error             TEXT
);

CREATE TABLE IF NOT EXISTS retrievals (
    id         INTEGER PRIMARY KEY,
    ts         TEXT NOT NULL,
    sim_ts     TEXT NOT NULL,
    message_id INTEGER,
    purpose    TEXT NOT NULL DEFAULT 'chat',   -- chat (shown to the dialogue model) | extract
    query      TEXT NOT NULL,
    hits       TEXT NOT NULL                   -- [{id, raw, alive, score, channels, in_prompt}]
);

CREATE TABLE IF NOT EXISTS memory_events (
    id         INTEGER PRIMARY KEY,
    ts         TEXT NOT NULL,
    sim_ts     TEXT NOT NULL,
    op         TEXT NOT NULL,                  -- add|dedup|supersede|forget|link|touch
    memory_id  INTEGER,
    message_id INTEGER,                        -- triggering message
    detail     TEXT NOT NULL DEFAULT '{}'
);
"""

TRACE_TABLES = ("llm_calls", "retrievals", "memory_events")


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


class Tracer:
    def __init__(self, db: sqlite3.Connection, clock: Clock):
        self.db, self.clock = db, clock
        db.executescript(TRACE_SCHEMA)
        self._local = threading.local()

    # ---------- causal context ----------

    @property
    def message_id(self) -> int | None:
        return getattr(self._local, "message_id", None)

    @contextmanager
    def cause(self, message_id: int | None):
        """Memory events inside this block are attributed to this message."""
        prev = self.message_id
        self._local.message_id = message_id
        try:
            yield
        finally:
            self._local.message_id = prev

    def _stamps(self) -> tuple[str, str]:
        return wall_now().isoformat(timespec="milliseconds"), iso(self.clock.now())

    # ---------- writers ----------

    def llm_call(self, *, purpose: str, model: str, request, response: str | None, prompt_tokens=None,
                 completion_tokens=None, cost=None, latency_ms=None, error: str | None = None) -> int:
        ts, sim = self._stamps()
        return self.db.execute(
            "INSERT INTO llm_calls(ts, sim_ts, purpose, model, request, response, prompt_tokens, "
            "completion_tokens, cost, latency_ms, error) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ts, sim, purpose, model, _json(request), response, prompt_tokens, completion_tokens, cost,
             latency_ms, error)).lastrowid

    def retrieval(self, *, message_id: int | None, query: str, hits: list[dict], purpose: str = "chat") -> int:
        ts, sim = self._stamps()
        return self.db.execute(
            "INSERT INTO retrievals(ts, sim_ts, message_id, purpose, query, hits) VALUES (?, ?, ?, ?, ?, ?)",
            (ts, sim, message_id, purpose, query, _json(hits))).lastrowid

    def memory_event(self, op: str, memory_id: int | None, detail: dict | None = None) -> None:
        ts, sim = self._stamps()
        self.db.execute(
            "INSERT INTO memory_events(ts, sim_ts, op, memory_id, message_id, detail) VALUES (?, ?, ?, ?, ?, ?)",
            (ts, sim, op, memory_id, self.message_id, _json(detail or {})))

    # ---------- readers ----------

    def marks(self) -> dict[str, int]:
        """Highest row id per table: rows after these marks were written later (e.g. in a probe fork)."""
        return {t: self.db.execute(f"SELECT COALESCE(MAX(id), 0) FROM {t}").fetchone()[0]
                for t in TRACE_TABLES + ("messages",)}

    def totals(self, since: dict[str, int] | None = None) -> dict:
        after = (since or {}).get("llm_calls", 0)
        rows = self.db.execute(
            "SELECT purpose, COUNT(*) n, COALESCE(SUM(prompt_tokens), 0) p, COALESCE(SUM(completion_tokens), 0) c, "
            "COALESCE(SUM(cost), 0) cost, SUM(error IS NOT NULL) errors FROM llm_calls WHERE id > ? GROUP BY purpose",
            (after,)).fetchall()
        by = {r["purpose"]: {"calls": r["n"], "prompt_tokens": r["p"], "completion_tokens": r["c"],
                             "cost": round(r["cost"], 6), "errors": r["errors"]} for r in rows}
        return {
            "calls": sum(v["calls"] for v in by.values()),
            "prompt_tokens": sum(v["prompt_tokens"] for v in by.values()),
            "completion_tokens": sum(v["completion_tokens"] for v in by.values()),
            "cost": round(sum(v["cost"] for v in by.values()), 6),
            "by_purpose": by,
        }


def export_jsonl(db: sqlite3.Connection, out_dir: Path, *, since: dict[str, int] | None = None,
                 extra: dict | None = None, tables=TRACE_TABLES + ("messages",), append: bool = False) -> None:
    """Mirror trace tables (rows after `since`) to <table>.jsonl, adding `extra` fields to every row."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for table in tables:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
            continue
        rows = db.execute(f"SELECT * FROM {table} WHERE id > ? ORDER BY id",
                          ((since or {}).get(table, 0),)).fetchall()
        with open(out_dir / f"{table}.jsonl", "a" if append else "w", encoding="utf-8") as f:
            for r in rows:
                row = dict(r)
                for key in ("request", "hits", "detail", "context_ids"):
                    if isinstance(row.get(key), str):
                        try:
                            row[key] = json.loads(row[key])
                        except json.JSONDecodeError:
                            pass
                row.update(extra or {})
                f.write(_json(row) + "\n")
