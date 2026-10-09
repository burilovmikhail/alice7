"""Prospective memory with a notion of "later" (spec §6.8). Replaces V2's intentions in V3 (switch `later`).

V2's flaw (article §4): an intention to remind the user "next time" was closed in the conversation that created
it, and a copy was closed by an unrelated answer. Here an intention carries `not_before` (the end of the creating
session): it cannot be fulfilled before. Fulfilment needs the observer to quote the part of the answer that
carries it out, and the quote must be in the answer. A due date makes it press (pressure) when it comes.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np

from ..common.clock import iso
from ..common.timefmt import ago
from ..v1.session import Session
from ..v1.store import MemoryStore
from ..v2.context import Section
from ..v2.intentions import EARLY_MESSAGES, EXPIRE_DAYS, SAME_INTENTION_SIM, SHOWN, parse_due

log = logging.getLogger(__name__)

TITLE = "## On your mind"
FRAMING = ("Things you meant to do or bring up with the user, from earlier conversations or from your own "
           "thoughts since.")


@dataclass
class Intention:
    id: int
    content: str
    not_before: str
    due: str | None
    source: str
    status: str
    created_at: str


def _intention(r) -> Intention:
    return Intention(r["id"], r["content"], r["not_before"], r["due"], r["source"], r["status"], r["created_at"])


class LaterIntentions:
    def __init__(self, store: MemoryStore, session_gap_hours: float):
        self.store, self.db, self.gap = store, store.db, session_gap_hours

    def open(self) -> list[Intention]:
        return [_intention(r) for r in self.db.execute("SELECT * FROM intentions_v3 WHERE status='open' ORDER BY id")]

    def get(self, intention_id) -> Intention | None:
        r = self.db.execute("SELECT * FROM intentions_v3 WHERE id=?", (intention_id,)).fetchone()
        return _intention(r) if r else None

    def add(self, content: str, *, due=None, source: str, message_id: int | None = None,
            session_id: int | None = None, not_before: datetime | None = None) -> int | None:
        content = (content or "").strip()
        if not content:
            return None
        vec = self.store.embed_one(content)
        for r in self.db.execute("SELECT id, content, embedding FROM intentions_v3 WHERE status='open'").fetchall():
            ov = np.frombuffer(r["embedding"], dtype=np.float32) if r["embedding"] else None
            same = (float(ov @ vec) >= SAME_INTENTION_SIM) if vec is not None and ov is not None else \
                r["content"].casefold() == content.casefold()
            if same:
                return r["id"]
        now = self.store.clock.now()
        # In a conversation: not before it ends (the session gap after now is the earliest it can be over)
        not_before = not_before or (now + timedelta(hours=self.gap) if session_id is not None else now)
        return self.db.execute(
            "INSERT INTO intentions_v3(content, not_before, due, source, message_id, session_id, embedding, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (content, iso(not_before), parse_due(due), source, message_id, session_id,
             vec.tobytes() if vec is not None else None, iso(now))).lastrowid

    def fulfil(self, intention_id: int, *, message_id: int, answer: str, quote: str) -> bool:
        """Closed only if it is "later" and the quoted part really is in the answer."""
        i = self.get(intention_id)
        quote = (quote or "").strip()
        now = self.store.clock.now()
        if i is None or i.status != "open" or now < datetime.fromisoformat(i.not_before):
            return False
        if len(quote) < 8 or " ".join(quote.split()).casefold() not in " ".join(answer.split()).casefold():
            return False
        self.db.execute("UPDATE intentions_v3 SET status='done', closed_by_message=?, evidence=?, closed_at=? "
                        "WHERE id=?", (message_id, quote, iso(now), intention_id))
        log.info("intention #%s done: %s", intention_id, quote[:80])
        return True

    def done_by_writing(self, intention_id: int, *, message_id: int, content: str) -> None:
        """The agent wrote to the user first about it: that is carrying it out."""
        self.db.execute("UPDATE intentions_v3 SET status='done', closed_by_message=?, evidence=?, closed_at=? "
                        "WHERE id=? AND status='open'", (message_id, content[:500], self.store.now(), intention_id))

    def drop(self, intention_id: int, reason: str = "") -> None:
        self.db.execute("UPDATE intentions_v3 SET status='dropped', evidence=?, closed_at=? WHERE id=? AND status='open'",
                        (reason, iso(self.store.clock.now()), intention_id))

    def expire(self, now: datetime) -> None:
        limit = iso(now - timedelta(days=EXPIRE_DAYS))
        for r in self.db.execute("SELECT id FROM intentions_v3 WHERE status='open' AND created_at < ?", (limit,)).fetchall():
            self.drop(r["id"], "expired")

    def due(self, now: datetime) -> list[Intention]:
        """Open intentions whose due day has come and that may already be acted on."""
        today = now.date().isoformat()
        return [i for i in self.open() if i.due and i.due <= today and datetime.fromisoformat(i.not_before) <= now]

    def to_surface(self, now: datetime, early: bool) -> list[Intention]:
        today = now.date().isoformat()
        ready = [i for i in self.open() if datetime.fromisoformat(i.not_before) <= now]
        due = [i for i in ready if i.due and i.due <= today]
        undated = [i for i in ready if not i.due]
        chosen = due + undated if early else [i for i in due if i.due == today]
        return sorted(chosen, key=lambda i: (i.due or "9999", i.id))[:SHOWN]


class LaterIntentionsMechanism:
    def __init__(self, intentions: LaterIntentions):
        self.intentions = intentions

    def system_section(self) -> Section | None:
        return None

    def memory_section(self, query: str, session: Session) -> Section | None:
        store = self.intentions.store
        now = store.clock.now()
        early = store.message_count(session.id) < EARLY_MESSAGES
        if early:
            self.intentions.expire(now)
        found = self.intentions.to_surface(now, early=early)
        if not found:
            return None
        lines = [f"- [#{i.id}] {i.content} (since {ago(i.created_at, now)}" + (f", for {i.due}" if i.due else "") + ")"
                 for i in found]
        return Section(TITLE, "\n".join(lines), FRAMING, {"intention_ids": [i.id for i in found]})
