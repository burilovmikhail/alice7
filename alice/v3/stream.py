"""The background stream (spec §6.2; Alice7 mind/drift.py): short thoughts on the cheap model, at a sim-time rhythm.

Each tick surfaces a few memories (recent and important, close to the last thought, now and then an old one) and
asks for one association: a continuation of the last thought or a drift elsewhere. These are working thoughts,
not memories: they live in stream_thoughts, and only a wake decides whether anything becomes lasting. Each gets a
novelty score; repetition adds almost nothing to pressure.
"""

import logging
import random
from datetime import datetime

import numpy as np

from ..common.clock import iso
from ..common.llm import LLM
from ..common.timefmt import ago
from ..v1.store import MemoryStore
from .affect import Affect, words
from .intentions import LaterIntentions
from .rhythm import ASLEEP, CONVERSATION
from .thoughts import Thoughts

log = logging.getLogger(__name__)

SEEDS = 3
RECENT = 12            # thoughts novelty is measured against
KEEP = 2000            # working memory of the stream
OLD_CHANCE = 0.25      # now and then an old, rarely recalled memory comes up

MODE_NOTE = {
    CONVERSATION: "A conversation is going on: the thought may be about it, something left unsaid or that caught you.",
    "idle": "No one is talking now. The thought is free.",
    ASLEEP: "It is night and quiet, like sleep: free associations, strange ones too, distant things mixed together.",
}

STREAM_PROMPT = """You are the background inner voice of Alice, a conversational companion. This is not a conversation and
not an answer: just a thought that passes by on its own. {mode}
Now: {now}. Mood: {mood}.

Continue your last thought, or let it drift to something the memories below bring up. One or two sentences,
first person, plain. No questions to anyone, no plans unless they come naturally. If nothing comes, say so briefly."""


def novelty(vec: np.ndarray | None, recent: list[np.ndarray]) -> float:
    """1 — completely new; about 0 — a repeat of a recent thought."""
    if vec is None or not recent:
        return 1.0
    return max(0.0, 1 - max(float(r @ vec) for r in recent)) ** 0.5


class Stream:
    def __init__(self, store: MemoryStore, llm: LLM, model: str, affect: Affect, intentions: LaterIntentions,
                 thoughts: Thoughts):
        self.store, self.db, self.llm, self.model = store, store.db, llm, model
        self.affect, self.intentions, self.thoughts = affect, intentions, thoughts

    def recent(self, limit: int = RECENT) -> list:
        return self.db.execute("SELECT * FROM stream_thoughts ORDER BY id DESC LIMIT ?", (limit,)).fetchall()

    def latest(self, within_minutes: int = 90):
        row = self.db.execute("SELECT * FROM stream_thoughts ORDER BY id DESC LIMIT 1").fetchone()
        if row is None:
            return None
        age = (self.store.clock.now() - datetime.fromisoformat(row["at"])).total_seconds() / 60
        return row if age <= within_minutes else None

    def _surface(self, last_vec: np.ndarray | None, now: datetime, rng: random.Random) -> list:
        """Recent and important, close to the last thought; sometimes an old, rarely recalled one."""
        memories = self.store.all_memories()
        if not memories:
            return []
        ids, mat = self.store.vectors()
        sim = {}
        if last_vec is not None and ids:
            sim = dict(zip(ids, (mat @ last_vec).tolist()))

        def score(m):
            age_days = max(0.0, (now - datetime.fromisoformat(m.valid_from)).total_seconds() / 86400)
            return m.importance * 0.5 ** (age_days / 7) + 0.5 * max(0.0, sim.get(m.id, 0.0))
        ranked = sorted(memories, key=lambda m: (-score(m), m.id))
        chosen = ranked[:SEEDS]
        rest = ranked[SEEDS:]
        if rest and rng.random() < OLD_CHANCE:
            old = sorted(rest, key=lambda m: (m.access_count, m.valid_from))[: max(1, len(rest) // 3)]
            chosen[-1] = rng.choice(old)
        return chosen

    def tick(self, mode: str) -> int | None:
        now = self.store.clock.now()
        rng = random.Random(iso(now))   # reproducible given the sim time
        recent = self.recent()
        last = recent[0] if recent else None
        last_vec = np.frombuffer(last["embedding"], dtype=np.float32) if last is not None and last["embedding"] else None
        seeds = self._surface(last_vec, now, rng)
        lines = [f"Your last thought ({ago(last['at'], now)}): {last['content']}" if last else "No earlier thought."]
        if seeds:
            lines.append("Memories that come up:\n" + "\n".join(f"- ({ago(m.valid_from, now)}) {m.content[:300]}"
                                                                  for m in seeds))
        threads = [i.content for i in self.intentions.open()][:3] + [q["content"] for q in self.thoughts.open_questions()][:2]
        if threads:
            lines.append("Still open for you:\n" + "\n".join(f"- {t}" for t in threads))
        try:
            text = self.llm.complete(STREAM_PROMPT.format(mode=MODE_NOTE.get(mode, MODE_NOTE["idle"]),
                                                          now=f"{now:%A %H:%M}", mood=words(self.affect.mood(now))),
                                     "\n\n".join(lines), purpose="stream", model=self.model, temperature=0.9)
        except Exception as e:
            log.warning("stream tick failed: %s", e)
            return None
        text = (text or "").strip()
        if not text:
            return None
        vec = self.store.embed_one(text)
        recent_vecs = [np.frombuffer(r["embedding"], dtype=np.float32) for r in recent if r["embedding"]]
        thought_id = self.db.execute(
            "INSERT INTO stream_thoughts(at, mode, content, seeds, novelty, embedding) VALUES (?, ?, ?, ?, ?, ?)",
            (iso(now), mode, text[:1000], "[" + ",".join(str(m.id) for m in seeds) + "]",
             round(novelty(vec, recent_vecs), 4), vec.tobytes() if vec is not None else None)).lastrowid
        self.db.execute("DELETE FROM stream_thoughts WHERE id <= ?", (thought_id - KEEP,))
        return thought_id
