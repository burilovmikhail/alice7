"""The monitor (spec §6.3; Alice7 mind/pressure.py, minus its personality dispositions (V4)): no model, just how much has accumulated.

    pressure = Σ fresh experience   importance · (1 + arousal) · recency · (1 + coherence with open threads)
             + Σ stream thoughts    novelty · recency · STREAM_WEIGHT
             + AFFECT_WEIGHT · unsettled feeling
             + Σ open threads       a tug that grows back after they were last considered
             + DUE_WEIGHT · due intentions not yet acted on today
    threshold = BASE_THRESHOLD · (1 + fatigue),   fatigue = Σ over recent wakes of 0.5^(minutes since / 60)

Safeguards against self-excitation are in the formula: "fresh" means since the last wake (a wake consumes what
triggered it), the stream counts only through novelty and at a fraction of external experience, each wake adds
fatigue, and there are caps per hour and per day. None of these numbers is ever shown to the model.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np

from ..common.clock import iso
from ..v1.store import MemoryStore
from .affect import Affect
from .intentions import LaterIntentions
from .thoughts import Thoughts

BASE_THRESHOLD = 3.0
RECENCY_HALF_HOURS = 6
STREAM_WEIGHT = 0.6          # Alice7: pull · novelty · 0.3 (own) · 2
AFFECT_WEIGHT = 1.5
THREAD_TUG = 0.15
THREAD_REST_HOURS = 24
THREADS_CAP = 1.0
DUE_WEIGHT = BASE_THRESHOLD   # something coming due is enough, on its own, to think about it
FATIGUE_HALF_MINUTES = 60
WAKES_PER_HOUR = 2


@dataclass
class Pressure:
    value: float
    threshold: float
    parts: dict[str, float] = field(default_factory=dict)
    fresh: list[int] = field(default_factory=list)
    stream: list[int] = field(default_factory=list)
    threads: list[str] = field(default_factory=list)   # "intention:3", "question:5"
    due: list[int] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return self.value >= self.threshold


def _hours(ts: str, now: datetime) -> float:
    return max(0.0, (now - datetime.fromisoformat(ts)).total_seconds() / 3600)


class Monitor:
    def __init__(self, store: MemoryStore, affect: Affect, intentions: LaterIntentions, thoughts: Thoughts,
                 use_affect):
        self.store, self.db = store, store.db
        self.affect, self.intentions, self.thoughts = affect, intentions, thoughts
        self.use_affect = use_affect   # callable: the affect switch

    def wakes_since(self, since: datetime) -> list[str]:
        return [r[0] for r in self.db.execute("SELECT at FROM wakes WHERE at > ? ORDER BY at", (iso(since),))]

    def fatigue(self, now: datetime) -> float:
        return sum(0.5 ** (_hours(at, now) * 60 / FATIGUE_HALF_MINUTES)
                   for at in self.wakes_since(now - timedelta(hours=12)))

    def measure(self, now: datetime, since: str, acted_on_today: set[int]) -> Pressure:
        intentions = [i for i in self.intentions.open() if datetime.fromisoformat(i.not_before) <= now]
        questions = self.thoughts.open_questions()
        thread_vecs = [np.frombuffer(r["embedding"], dtype=np.float32) for r in self.db.execute(
            "SELECT embedding FROM intentions_v3 WHERE status='open' AND embedding IS NOT NULL")]
        thread_vecs += [np.frombuffer(q["embedding"], dtype=np.float32) for q in questions if q["embedding"]]
        threads_mat = np.stack(thread_vecs) if thread_vecs else None

        # 1. Fresh experience since the last wake
        fresh_value, fresh = 0.0, []
        rows = self.db.execute("SELECT id, importance, created_at, embedding FROM memories "
                               "WHERE created_at > ? AND valid_to IS NULL", (since,)).fetchall()
        arousal = self.affect.arousal_of(r["id"] for r in rows) if self.use_affect() else {}
        for r in rows:
            coherence = 0.0
            if threads_mat is not None and r["embedding"]:
                coherence = max(0.0, float(np.max(threads_mat @ np.frombuffer(r["embedding"], dtype=np.float32))))
            recency = 0.5 ** (_hours(r["created_at"], now) / RECENCY_HALF_HOURS)
            fresh_value += r["importance"] * (1 + arousal.get(r["id"], 0.0)) * recency * (1 + coherence)
            fresh.append(r["id"])

        # 2. The stream, only through novelty
        stream_value, stream = 0.0, []
        for r in self.db.execute("SELECT id, at, novelty FROM stream_thoughts WHERE consumed=0 AND at > ?", (since,)):
            stream_value += r["novelty"] * 0.5 ** (_hours(r["at"], now) / RECENCY_HALF_HOURS) * STREAM_WEIGHT
            stream.append(r["id"])

        # 3. Unsettled feeling
        affect_value = AFFECT_WEIGHT * self.affect.unsettled(now) if self.use_affect() else 0.0

        # 4. Open threads tug, but rest after being considered
        thread_value, pulling = 0.0, []
        for i in intentions:
            tug = THREAD_TUG * (1 - 0.5 ** (_hours(i.created_at, now) / THREAD_REST_HOURS))
            thread_value += tug
            pulling.append(f"intention:{i.id}")
        for q in questions:
            tug = THREAD_TUG * (1 - 0.5 ** (_hours(q["last_considered"] or q["created_at"], now) / THREAD_REST_HOURS))
            thread_value += tug
            pulling.append(f"question:{q['id']}")
        thread_value = min(thread_value, THREADS_CAP)

        # 5. What has come due
        due = [i.id for i in self.intentions.due(now) if i.id not in acted_on_today]
        due_value = DUE_WEIGHT * len(due)

        threshold = BASE_THRESHOLD * (1 + self.fatigue(now))
        parts = {"fresh": fresh_value, "stream": stream_value, "affect": affect_value, "threads": thread_value,
                 "due": due_value}
        return Pressure(round(sum(parts.values()), 3), round(threshold, 3), {k: round(v, 3) for k, v in parts.items()},
                        fresh, stream, pulling, due)

    def log(self, now: datetime, p: Pressure, woke: bool) -> None:
        self.db.execute("INSERT INTO pressure_log(at, value, threshold, parts, woke) VALUES (?, ?, ?, ?, ?)",
                        (iso(now), p.value, p.threshold, json.dumps(p.parts), int(woke)))

    def capped(self, now: datetime, per_day: int) -> str | None:
        """Why a wake may not happen now, or None."""
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if len(self.wakes_since(day_start)) >= per_day:
            return "daily cap"
        if len(self.wakes_since(now - timedelta(hours=1))) >= WAKES_PER_HOUR:
            return "hourly cap"
        return None
