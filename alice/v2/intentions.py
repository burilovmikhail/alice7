"""Prospective memory: what the agent promised or decided to do in a later conversation (spec §6.6).

Created from the agent's own commitments (self-observation) and by self-review. Surfaced at the start of a
conversation and when due; closed when an answer carries them out, dropped after 30 days or by self-review.
Unlike V3's delayed intention (E9), a V2 intention can only come back when the user starts a conversation.
"""

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from ..common.timefmt import ago
from ..v1.session import Session
from ..v1.store import MemoryStore
from .context import Section

log = logging.getLogger(__name__)

EARLY_MESSAGES = 4         # like V1's look back at the previous session: only at the start of a conversation
SHOWN = 3
EXPIRE_DAYS = 30
SAME_INTENTION_SIM = 0.88

TITLE = "## On your mind"
FRAMING = "Things you meant to do or bring up with the user, from earlier conversations."

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass
class Intention:
    id: int
    content: str
    due: str | None          # YYYY-MM-DD or None
    source: str
    status: str
    created_at: str


def _intention(row) -> Intention:
    return Intention(row["id"], row["content"], row["due_from"], row["source"], row["status"], row["created_at"])


def parse_due(value) -> str | None:
    """The model resolves "next week" itself (it sees today's date); anything but YYYY-MM-DD means no date."""
    value = str(value or "").strip()[:10]
    if not _DATE.match(value):
        return None
    try:
        date.fromisoformat(value)
    except ValueError:
        return None
    return value


class IntentionStore:
    def __init__(self, store: MemoryStore):
        self.store, self.db = store, store.db

    def open(self) -> list[Intention]:
        return [_intention(r) for r in self.db.execute(
            "SELECT * FROM intentions WHERE status='open' ORDER BY id")]

    def get(self, intention_id) -> Intention | None:
        row = self.db.execute("SELECT * FROM intentions WHERE id=?", (intention_id,)).fetchone()
        return _intention(row) if row else None

    def add(self, content: str, *, due=None, source: str, message_id: int | None = None,
            session_id: int | None = None) -> int | None:
        content = (content or "").strip()
        if not content:
            return None
        vec = self.store.embed_one(content)
        for other in self.open():
            ov = self.store.embed_one(other.content) if vec is not None else None
            same = (float(ov @ vec) >= SAME_INTENTION_SIM) if ov is not None else \
                other.content.casefold() == content.casefold()
            if same:
                return other.id
        due = parse_due(due)
        return self.db.execute(
            "INSERT INTO intentions(content, due_from, due_to, source, message_id, session_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (content, due, due, source, message_id, session_id, self.store.now())).lastrowid

    def close(self, intention_id: int, status: str, message_id: int | None = None) -> None:
        self.db.execute("UPDATE intentions SET status=?, closed_by_message=?, closed_at=? WHERE id=? AND status='open'",
                        (status, message_id, self.store.now(), intention_id))
        log.info("intention #%s %s", intention_id, status)

    def expire(self, now: datetime) -> None:
        limit = (now - timedelta(days=EXPIRE_DAYS)).isoformat(timespec="seconds")
        for row in self.db.execute("SELECT id FROM intentions WHERE status='open' AND created_at < ?", (limit,)).fetchall():
            self.close(row["id"], "dropped")

    def to_surface(self, now: datetime, early: bool) -> list[Intention]:
        """At the start of a conversation: open intentions that are due or undated. Later: only those due today."""
        today = now.date().isoformat()
        due = [i for i in self.open() if i.due is not None and i.due <= today]
        undated = [i for i in self.open() if i.due is None]
        chosen = due + undated if early else [i for i in due if i.due == today]
        return sorted(chosen, key=lambda i: (i.due or "9999", i.id))[:SHOWN]


class IntentionsMechanism:
    """The `intentions` switch."""

    def __init__(self, intentions: IntentionStore):
        self.intentions = intentions

    def system_section(self) -> Section | None:
        return None

    def memory_section(self, query: str, session: Session) -> Section | None:
        store = self.intentions.store
        now = store.clock.now()
        self.intentions.expire(now)
        found = self.intentions.to_surface(now, early=store.message_count(session.id) < EARLY_MESSAGES)
        if not found:
            return None
        lines = [f"- {i.content} (since {ago(i.created_at, now)}" + (f", for {i.due}" if i.due else "") + ")"
                 for i in found]
        return Section(TITLE, "\n".join(lines), FRAMING, {"intention_ids": [i.id for i in found]})
