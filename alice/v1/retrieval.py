"""Hybrid retrieval: vector + full-text + entities + time range + one hop over links, weighted by retention."""

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime

import numpy as np

from ..common.text import fts_query
from .store import Memory, MemoryStore

# ---------- constants (from Alice7; kept together for later tuning) ----------
SEMANTIC_TOP_K = 30
SEMANTIC_CUTOFF = 0.35
SEMANTIC_WEIGHT = 0.6
FTS_TOP_K = 30
FTS_WEIGHT = 0.3
FTS_RANK_DECAY = 0.3
ENTITY_WEIGHT = 0.3
TIME_EPISODE_WEIGHT = 0.5
TIME_FACT_WEIGHT = 0.2
HOP_SEEDS = 5
HOP_LED_TO = 0.5
HOP_OTHER = 0.4
IMPORTANCE_BASE, IMPORTANCE_GAIN = 0.6, 0.4
ALIVE_BASE, ALIVE_GAIN = 0.55, 0.45
MIN_SCORE = 0.15
LIMIT = 12
HALF_LIFE_DAYS = 30.0


def retention(age_days: float, importance: float, access_count: int, causal_out: int) -> float:
    """How "alive" a memory is, 0..1. The half-life stretches with importance, rehearsal and consequences.
    Decay affects ranking only; nothing is ever dropped by it."""
    half_life = (HALF_LIFE_DAYS
                 * (0.5 + importance)
                 * (1 + 0.3 * math.log1p(access_count))
                 * (1 + 0.5 * math.log1p(causal_out)))
    return 0.5 ** (max(age_days, 0.0) / half_life)


@dataclass
class Candidate:
    memory: Memory
    raw: float
    channels: dict[str, float]
    alive: float = 0.0
    score: float = 0.0
    selected: bool = False      # passed the threshold and the limit
    excluded: str | None = None  # "core" | "below_threshold" | "over_limit"
    in_prompt: bool = False      # survived the token budget (set by the context builder)

    def record(self) -> dict:
        return {"id": self.memory.id, "kind": self.memory.kind, "content": self.memory.content,
                "raw": round(self.raw, 4), "alive": round(self.alive, 4), "score": round(self.score, 4),
                "channels": {k: round(v, 4) for k, v in self.channels.items()},
                "selected": self.selected, "excluded": self.excluded, "in_prompt": self.in_prompt}


@dataclass
class SearchResult:
    hits: list[Candidate] = field(default_factory=list)        # ranked, at most `limit`
    candidates: list[Candidate] = field(default_factory=list)  # everything scored, for the trace

    def records(self) -> list[dict]:
        return [c.record() for c in sorted(self.candidates, key=lambda c: -c.score)]


def search(store: MemoryStore, query: str, *, now: datetime, limit: int = LIMIT,
           date_range: tuple[date, date] | None = None, include_core: bool = False,
           min_score: float = MIN_SCORE) -> SearchResult:
    if not query.strip() and not date_range:
        return SearchResult()
    channels: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    # 1. Semantic similarity
    qv = store.embed_one(query)
    ids, mat = store.vectors()
    if qv is not None and ids:
        sims = mat @ qv
        for i in np.argsort(-sims)[:SEMANTIC_TOP_K]:
            if sims[i] < SEMANTIC_CUTOFF:
                break
            channels[ids[i]]["semantic"] += SEMANTIC_WEIGHT * float(sims[i])

    # 2. Word overlap (names, terms — what vectors sometimes miss)
    if q := fts_query(query):
        for rank, mid in enumerate(store.fts(q, FTS_TOP_K)):
            channels[mid]["fts"] += FTS_WEIGHT / (1 + FTS_RANK_DECAY * rank)

    # 3. Mentioned entities -> everything linked to them
    entity_ids = [e.id for e in store.entities_in_text(query)]
    for mid in store.memories_of_entities(entity_ids):
        channels[mid]["entity"] += ENTITY_WEIGHT

    # 4. "Yesterday", "last week" -> records from that period
    if date_range:
        start, end = date_range
        for mid, kind in store.memories_in_range(start.isoformat(), end.isoformat() + "T99"):
            channels[mid]["time"] += TIME_EPISODE_WEIGHT if kind == "episode" else TIME_FACT_WEIGHT

    # 5. One hop over links from the top seeds: episode <-> its facts, cause <-> effect
    raw = {mid: sum(ch.values()) for mid, ch in channels.items()}
    seeds = sorted(raw, key=raw.get, reverse=True)[:HOP_SEEDS]
    for src, dst, relation in store.links_of(seeds):
        for origin, other in ((src, dst), (dst, src)):
            if origin in seeds:
                channels[other]["hop"] += (HOP_LED_TO if relation == "led_to" else HOP_OTHER) * raw[origin]

    memories = store.memories_by_ids(channels)  # active only: superseded/forgotten drop out here
    out_degree = store.causal_out_degree(memories)
    result = SearchResult()
    for mid, m in memories.items():
        ch = dict(channels[mid])
        c = Candidate(m, sum(ch.values()), ch)
        # Age counts from the last time the memory was recalled: rehearsal refreshes it
        last_touch = max(m.created_at, m.last_accessed or m.created_at)
        age_days = (now - datetime.fromisoformat(last_touch)).total_seconds() / 86400
        c.alive = retention(age_days, m.importance, m.access_count, out_degree.get(mid, 0))
        c.score = c.raw * (IMPORTANCE_BASE + IMPORTANCE_GAIN * m.importance) * (ALIVE_BASE + ALIVE_GAIN * c.alive)
        if m.tier == "core" and not include_core:
            c.excluded = "core"  # already in the system prompt
        elif c.score < min_score:
            c.excluded = "below_threshold"
        result.candidates.append(c)
    ranked = sorted((c for c in result.candidates if c.excluded is None), key=lambda c: -c.score)
    for c in ranked[limit:]:
        c.excluded = "over_limit"
    result.hits = ranked[:limit]
    for c in result.hits:
        c.selected = True
    return result
