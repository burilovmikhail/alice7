"""What the agent thinks on its own and keeps (spec §6.4, D6): thoughts from wakes and sleep, open questions.

Kept apart from V1's memory: lived experience stays in V1's store, the agent's own thoughts live here and reach
the prompt under their own heading, so the agent can tell what it was told from what it told itself.
"""

from datetime import datetime

import numpy as np

from ..common.clock import iso
from ..common.timefmt import ago
from ..v1.session import Session
from ..v1.store import MemoryStore
from ..v2.context import Section

THOUGHTS_SHOWN = 2
THOUGHT_SIM = 0.5
STREAM_TITLE = "## In the back of your mind"
STREAM_FRAMING = "A thought that passed through your mind just now, on its own."
THOUGHTS_TITLE = "## What you thought on your own"
THOUGHTS_FRAMING = "Your own thoughts from quiet moments, not things the user told you."
QUESTIONS_TITLE = "## Questions you keep coming back to"


def _vec(blob):
    return np.frombuffer(blob, dtype=np.float32) if blob else None


class Thoughts:
    def __init__(self, store: MemoryStore):
        self.store, self.db = store, store.db

    def add(self, content: str, *, source: str, source_id: int | None) -> int | None:
        content = (content or "").strip()
        if not content:
            return None
        vec = self.store.embed_one(content)
        return self.db.execute("INSERT INTO thoughts(at, source, source_id, content, embedding) VALUES (?, ?, ?, ?, ?)",
                               (self.store.now(), source, source_id, content,
                                vec.tobytes() if vec is not None else None)).lastrowid

    def relevant(self, query: str, limit: int = THOUGHTS_SHOWN) -> list:
        qv = self.store.embed_one(query) if query.strip() else None
        if qv is None:
            return []
        rows = self.db.execute("SELECT * FROM thoughts WHERE embedding IS NOT NULL").fetchall()
        scored = sorted(((float(_vec(r["embedding"]) @ qv), r) for r in rows), key=lambda x: (-x[0], -x[1]["id"]))
        return [r for sim, r in scored if sim >= THOUGHT_SIM][:limit]

    # ---------- questions ----------

    def ask(self, content: str, *, source: str, source_id: int | None) -> int | None:
        content = (content or "").strip()
        if not content:
            return None
        vec = self.store.embed_one(content)
        return self.db.execute(
            "INSERT INTO questions(content, source, source_id, embedding, created_at, last_considered) "
            "VALUES (?, ?, ?, ?, ?, ?)", (content, source, source_id, vec.tobytes() if vec is not None else None,
                                          self.store.now(), self.store.now())).lastrowid

    def open_questions(self) -> list:
        return self.db.execute("SELECT * FROM questions WHERE status='open' ORDER BY id").fetchall()

    def resolve(self, question_id: int, answer: str) -> bool:
        return bool(self.db.execute(
            "UPDATE questions SET status='resolved', answer=?, resolved_at=? WHERE id=? AND status='open'",
            (answer, self.store.now(), question_id)).rowcount)

    def considered(self, question_ids, at: datetime) -> None:
        self.db.executemany("UPDATE questions SET last_considered=? WHERE id=?", [(iso(at), i) for i in question_ids])


class ThoughtsMechanism:
    """Context sections: the latest stream thought in conversation, relevant own thoughts, open questions."""

    def __init__(self, thoughts: Thoughts, latest_stream, show_stream, show_own):
        self.thoughts, self.latest_stream = thoughts, latest_stream
        self.show_stream, self.show_own = show_stream, show_own   # callables: switch states

    def system_section(self) -> Section | None:
        return None

    def memory_section(self, query: str, session: Session) -> Section | None:
        now = self.thoughts.store.clock.now()
        lines, shown = [], []
        if self.show_stream() and (latest := self.latest_stream()):
            lines.append(f"{STREAM_TITLE}\n{STREAM_FRAMING}\n{latest['content']}")
        if self.show_own():
            own = self.thoughts.relevant(query)
            if own:
                lines.append(f"{THOUGHTS_TITLE}\n{THOUGHTS_FRAMING}\n" + "\n".join(
                    f"- ({ago(r['at'], now)}) {r['content']}" for r in own))
                shown = [r["id"] for r in own]
            questions = self.thoughts.open_questions()[:2]
            if questions and self.thoughts.store.message_count(session.id) < 4:
                lines.append(f"{QUESTIONS_TITLE}\n" + "\n".join(f"- {q['content']}" for q in questions))
        if not lines:
            return None
        title, _, body = "\n\n".join(lines).partition("\n")
        return Section(title, body, "", {"thought_ids": shown})
