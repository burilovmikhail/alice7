"""Writing first (spec §6.6): the agent opens a conversation, within strict limits."""

from datetime import datetime

from ..common.clock import iso
from ..v1.session import Session
from . import rhythm
from .config import V3Config


class Initiative:
    def __init__(self, agent, cfg: V3Config):
        self.agent, self.cfg = agent, cfg
        self.db = agent.db

    def blocked(self, now: datetime) -> str | None:
        """Why the agent may not write first now, or None."""
        if not self.agent.v3_switches.initiative:
            return "initiative off"
        if not rhythm.awake(now, self.cfg):
            return "outside the awake window"
        day = iso(now.replace(hour=0, minute=0, second=0))
        if self.db.execute("SELECT COUNT(*) FROM outbox WHERE at >= ?", (day,)).fetchone()[0] >= self.cfg.writes_per_day:
            return "daily cap"
        last = self.db.execute("SELECT message_id FROM outbox ORDER BY message_id DESC LIMIT 1").fetchone()
        if last and not self.db.execute("SELECT 1 FROM messages WHERE role='user' AND id > ?", (last[0],)).fetchone():
            return "the last message written first has no reply yet"
        return None

    def write(self, content: str, *, wake_id: int | None, intention_id: int | None) -> dict | None:
        content = (content or "").strip()
        now = self.agent.clock.now()
        if not content or self.blocked(now):
            return None
        if self.agent.session is None:
            self.agent.session = Session.start(self.agent.store, self.agent.llm, self.agent.cfg)
        message_id = self.agent.session.add("assistant", content)
        self.db.execute("INSERT INTO outbox(message_id, at, wake_id, intention_id, content) VALUES (?, ?, ?, ?, ?)",
                        (message_id, iso(now), wake_id, intention_id, content))
        return {"at": iso(now), "content": content, "message_id": message_id, "wake_id": wake_id,
                "intention_id": intention_id}
