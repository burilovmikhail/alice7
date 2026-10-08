"""Affect: a fast reaction and a slow mood (spec §6.7; Alice7 memory/affect.py).

Functional, not a claim about experience: an appraisal of what happened that persists for a while and colors
what comes next. The fast layer follows each appraisal and relaxes toward the mood within minutes; the mood
absorbs a little of every appraisal and relaxes toward a fixed temperament over days. Relaxation is computed
from sim time, so silence changes mood too. Thoughts (wakes) move it at a third of the weight of lived exchanges.

Affect enters pressure (unsettled feeling) and the prompt (mood in words). It does not touch V1's retrieval:
memories are tagged with the moment's affect, and V3's own processes read the tags; V1's ranking stays frozen.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime

from ..common.clock import iso
from ..v1.session import Session
from ..v1.store import MemoryStore
from ..v2.context import Section

EMOTIONS = ("curiosity", "joy", "warmth", "gratitude", "pride", "surprise", "calm",
            "anxiety", "sadness", "irritation", "awkwardness", "confusion", "boredom")

FAST_HALF_LIFE_MIN = 20       # the fast layer halves its distance to the mood in 20 minutes
FAST_FOLLOW = 0.6             # how much a new appraisal overrides the current fast state
MOOD_RATE = 0.08              # share of an appraisal that settles into the mood
MOOD_HALF_LIFE_DAYS = 7       # without anything happening, the mood halves its distance to temperament in a week
THOUGHT_WEIGHT = 1 / 3        # what the agent thought moves it less than what it lived

MOOD_TITLE = "## Your mood"
MOOD_FRAMING = "How you have been feeling lately, carried over from your recent conversations and thoughts."


@dataclass
class State:
    valence: float
    arousal: float
    emotions: dict[str, float] = field(default_factory=dict)
    cause: str = ""
    at: str = ""

    def top(self, n: int = 3, floor: float = 0.2) -> list[tuple[str, float]]:
        return sorted(((k, v) for k, v in self.emotions.items() if v >= floor), key=lambda x: -x[1])[:n]


TEMPERAMENT = State(valence=0.2, arousal=0.35, emotions={"curiosity": 0.3, "calm": 0.3})


def clamp(valence, arousal, emotions) -> State:
    def num(x, lo, hi):
        try:
            return max(lo, min(hi, float(x or 0)))
        except (TypeError, ValueError):
            return 0.0
    e = {k: num(v, 0, 1) for k, v in (emotions or {}).items() if k in EMOTIONS} if isinstance(emotions, dict) else {}
    return State(num(valence, -1, 1), num(arousal, 0, 1), e)


def mix(a: State, b: State, k: float) -> State:
    """a + k·(b − a) in every dimension."""
    names = set(a.emotions) | set(b.emotions)
    emotions = {n: a.emotions.get(n, 0) + k * (b.emotions.get(n, 0) - a.emotions.get(n, 0)) for n in names}
    return State(a.valence + k * (b.valence - a.valence), a.arousal + k * (b.arousal - a.arousal),
                 {n: round(v, 3) for n, v in emotions.items() if v >= 0.02}, b.cause or a.cause, b.at or a.at)


def relax(state: State, toward: State, seconds: float, half_life_seconds: float) -> State:
    k = 1 - 0.5 ** (max(seconds, 0) / half_life_seconds)
    out = mix(state, toward, k)
    out.cause, out.at = state.cause, state.at
    return out


def tone(v: float, a: float) -> str:
    if v >= 0.35:
        return "excited" if a >= 0.6 else "warm and light" if a >= 0.3 else "calm and content"
    if v <= -0.35:
        return "tense, anxious" if a >= 0.6 else "low" if a >= 0.3 else "flat, subdued"
    return "restless" if a >= 0.6 else "even" if a >= 0.3 else "quiet"


def words(state: State) -> str:
    feelings = ", ".join(name for name, _ in state.top())
    return tone(state.valence, state.arousal) + (f" ({feelings})" if feelings else "")


class Affect:
    def __init__(self, store: MemoryStore):
        self.store, self.db = store, store.db

    def _latest(self, layer: str) -> State | None:
        row = self.db.execute("SELECT * FROM affect_states WHERE layer=? ORDER BY id DESC LIMIT 1", (layer,)).fetchone()
        if row is None:
            return None
        return State(row["valence"], row["arousal"], json.loads(row["emotions"]), row["cause"], row["at"])

    def mood(self, now: datetime | None = None) -> State:
        now = now or self.store.clock.now()
        last = self._latest("mood")
        if last is None:
            return State(**{**TEMPERAMENT.__dict__, "emotions": dict(TEMPERAMENT.emotions)})
        seconds = (now - datetime.fromisoformat(last.at)).total_seconds()
        return relax(last, TEMPERAMENT, seconds, MOOD_HALF_LIFE_DAYS * 86400)

    def current(self, now: datetime | None = None) -> State:
        """The fast layer, relaxed toward the (relaxed) mood."""
        now = now or self.store.clock.now()
        mood, fast = self.mood(now), self._latest("fast")
        if fast is None:
            return mood
        seconds = (now - datetime.fromisoformat(fast.at)).total_seconds()
        return relax(fast, mood, seconds, FAST_HALF_LIFE_MIN * 60)

    def unsettled(self, now: datetime | None = None) -> float:
        """How far the moment is from the background: |Δ arousal| + |Δ valence| (feeds pressure)."""
        cur, mood = self.current(now), self.mood(now)
        return max(0.0, cur.arousal - mood.arousal) + abs(cur.valence - mood.valence)

    def update(self, appraisal: State, *, cause: str, message_id: int | None = None, weight: float = 1.0) -> State:
        """A new appraisal: the fast layer follows, the mood absorbs a little."""
        now = self.store.clock.now()
        at = iso(now)
        fast = mix(self.current(now), appraisal, FAST_FOLLOW * weight)
        mood = mix(self.mood(now), appraisal, MOOD_RATE * weight)
        for layer, s in (("fast", fast), ("mood", mood)):
            self.db.execute(
                "INSERT INTO affect_states(at, layer, valence, arousal, emotions, cause, message_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (at, layer, round(s.valence, 4), round(s.arousal, 4), json.dumps(s.emotions), cause[:200], message_id))
        return fast

    def tag(self, memory_ids, state: State) -> None:
        self.db.executemany("INSERT OR REPLACE INTO memory_affect(memory_id, valence, arousal) VALUES (?, ?, ?)",
                            [(i, round(state.valence, 4), round(state.arousal, 4)) for i in memory_ids])

    def arousal_of(self, memory_ids) -> dict[int, float]:
        ids = list(memory_ids)
        if not ids:
            return {}
        q = ",".join("?" * len(ids))
        return {r[0]: r[1] for r in self.db.execute(
            f"SELECT memory_id, arousal FROM memory_affect WHERE memory_id IN ({q})", ids)}


class AffectMechanism:
    """The `affect` switch's part of the context: the mood in words in the system prompt."""

    def __init__(self, affect: Affect):
        self.affect = affect

    def system_section(self) -> Section | None:
        return Section(MOOD_TITLE, words(self.affect.mood()), MOOD_FRAMING)

    def memory_section(self, query: str, session: Session) -> Section | None:
        return None
