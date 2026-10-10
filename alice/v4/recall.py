"""Recall by activation (spec §6.11), in place of V1's search for V4's prompt (V1's code is unchanged).

V1 memories are ranked by a + 0.3·σ(B), with `a` the activations after the message's input has spread for 3 sim
minutes. The result has V1's SearchResult shape, so the context, the trace of retrievals and the gold-memory
scoring work as they do for V1. Same input at two moments gives different memories, because the field differs (T65).
"""

import numpy as np

from ..v1.retrieval import Candidate, SearchResult
from ..v1.store import MemoryStore
from . import constants as K
from .field import Field, sigmoid


def recall(store: MemoryStore, field: Field, a: np.ndarray, *, exclude_episodes: bool = False,
           limit: int = K.RECALL_LIMIT, min_score: float = K.RECALL_MIN) -> SearchResult:
    kinds = ("memory",) if exclude_episodes else ("memory", "episode")
    nodes = {field.ref[i]: i for i in np.flatnonzero(field.mask(*kinds))}
    memories = store.memories_by_ids(nodes)
    result = SearchResult()
    for mid, m in memories.items():
        i = nodes[mid]
        base = K.RECALL_BASE_WEIGHT * float(sigmoid(field.B[i]))
        c = Candidate(m, float(a[i]) + base, {"activation": float(a[i]), "base": base})
        c.alive, c.score = 1.0, c.raw
        if m.tier == "core":
            c.excluded = "core"
        elif c.score < min_score:
            c.excluded = "below_threshold"
        result.candidates.append(c)
    ranked = sorted((c for c in result.candidates if c.excluded is None), key=lambda c: (-c.score, c.memory.id))
    for c in ranked[limit:]:
        c.excluded = "over_limit"
    result.hits = ranked[:limit]
    for c in result.hits:
        c.selected = True
    return result
