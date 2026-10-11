"""Learning (spec §6.8): all local, all numeric, none performed by a model.

- base level (ACT-R) is in field.py: uses are recorded as activation crosses 0.5; unrehearsed nodes get hard to
  light: forgetting without deletion (T35);
- Hebbian: Δw_ij = η · a_i · a_j − λ · w_ij over co-active working-memory nodes; new edges between nodes co-active
  for 10 min; unused edges fade;
- prediction error (T34): the expected signal of a reaction is the activation-weighted mean signal of the traces
  that were in the reply's context; PE = signal − expected;
- online salience at creation (T37);
- reconsolidation (T36, switch): each recall moves a node's valence toward the current mood.
"""

import numpy as np

from . import constants as K
from .field import Field


def hebbian(field: Field, wm: list[int], dt: float, gain: float, coactive: dict, t: float) -> int:
    """Strengthen edges among co-active working-memory nodes; pairs co-active for 10 min get a new edge.
    `coactive`: (id_i, id_j) -> minutes, kept across steps. Returns the number of new edges."""
    pairs, new = set(), []
    for x, i in enumerate(wm):
        for j in wm[x + 1:]:
            key = (min(i, j), max(i, j))
            pairs.add(key)
            k = field.edge_at.get(key)
            if k is not None:
                field.w[k] = min(1.0, field.w[k] + dt * K.HEBB_ETA * gain * field.a[i] * field.a[j] * (1 - field.w[k]))
                continue
            ids = (int(field.ids[key[0]]), int(field.ids[key[1]]))
            coactive[ids] = coactive.get(ids, 0.0) + dt
            if coactive[ids] >= K.HEBB_NEW_AFTER_MIN:
                new.append((key[0], key[1], K.HEBB_NEW_W))
                del coactive[ids]
    live = {(int(field.ids[i]), int(field.ids[j])) for i, j in pairs}
    for ids in [p for p in coactive if p not in live]:   # co-activity has to be continuous
        del coactive[ids]
    return field.add_edges(new, learned=True) if new else 0


def fade(field: Field, minutes: float, nrem: bool) -> None:
    """λ · w over every edge; in NREM, edges under 0.05 fade five times faster (T75)."""
    if not len(field.w):
        return
    rate = np.full(len(field.w), K.HEBB_LAMBDA)
    if nrem:
        rate = np.where(field.w < K.NREM_WEAK_EDGE, rate * K.NREM_WEAK_DECAY, rate)
    field.w = field.w * (1 - rate) ** minutes


def salience(parts: dict[str, float]) -> float:
    w = K.SALIENCE_WEIGHTS
    return float(sum(w[k] * min(1.0, max(0.0, parts.get(k, 0.0))) for k in w) / sum(w.values()))


def salience_parts(field: Field, vec: np.ndarray | None, t: float, *, valence: float = 0.0, arousal: float = 0.0,
                   pe: float = 0.0, self_relevance: float = 0.0) -> dict[str, float]:
    """novelty + |valence| + arousal + goal relevance + |PE| + recurrence + self-relevance, each 0..1."""
    sims = field.similarities(vec)
    threads = field.mask("intention", "question") & (field.u > 0)
    recent = (t - field.created) <= K.RECURRENCE_DAYS * 1440
    return {
        "novelty": 1.0 - float(max(0.0, sims.max())) if len(sims) and vec is not None else 1.0,
        "valence": abs(valence), "arousal": arousal,
        "goal": float(max(0.0, sims[threads].max())) if threads.any() else 0.0,
        "pe": abs(pe),
        "recurrence": min(1.0, float(((sims >= K.RECURRENCE_COS) & recent).sum()) / K.RECURRENCE_FULL),
        "self": self_relevance,
    }


def expected_signal(signals: list[float], activations: list[float]) -> float:
    """The activation-weighted mean signal of the traces the reply was written with (0 with none)."""
    total = sum(activations)
    return float(sum(s * a for s, a in zip(signals, activations)) / total) if total > 0 else 0.0


def reconsolidate(field: Field, positions, mood: float) -> None:
    for i in positions:
        field.valence[i] += K.RECONSOLIDATION * (mood - field.valence[i])


def pool_duplicates(field: Field, positions: list[int]) -> int:
    """Near-duplicates (cos ≥ 0.82) get a strong edge and pool their base level (no model, no writes to V1)."""
    if field.emb is None:
        return 0
    pairs = 0
    for i in positions:
        sims = field.similarities(field.emb[i])
        for j in np.flatnonzero(sims >= K.DUPLICATE_COS):
            j = int(j)
            if j == i or field.kind[j] != field.kind[i] or field.weight(i, j) >= K.DUPLICATE_W:
                continue
            field.add_edges([(i, j, K.DUPLICATE_W)], learned=True)
            pooled = sorted(set(field.uses[i]) | set(field.uses[j]))[-K.USES_KEPT:]
            field.uses[i], field.uses[j] = list(pooled), list(pooled)
            pairs += 1
    return pairs
