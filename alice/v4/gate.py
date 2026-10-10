"""The gate (spec §6.5, T53, T122–T124): when the model is called. Two numbers, both required.

    coherence = E(K) · stability(K)        how well the coalition hangs together, and for how long
    du/dt     = −u/τ_u + Σ c_s · I_s       urgency, a leaky integrator of several kinds of pressure
    brake     = b₀ · (1 + 2·fatigue) · (1 + S) · mode_factor    closed by default
    fire  ⇔  coherence ≥ θ_c(boredom)  ∧  u ≥ brake  ∧  caps allow

A source of urgency contributes only while at least two different kinds are above their floors (T122, T125):
one strong pressure alone is not yet a reason to think. Coherent without urgency is a "yawn"; urgent without
coherence is "worry without shape". Both are logged as near-misses and call no model.
"""

from collections import deque
from dataclasses import dataclass, field

from . import constants as K
from .attention import jaccard
from .field import Field


@dataclass
class Reading:
    coherence: float = 0.0
    energy: float = 0.0
    stability: float = 0.0
    theta: float = 0.0
    urgency: float = 0.0
    brake: float = float("inf")
    sources: dict[str, float] = field(default_factory=dict)
    counted: bool = False

    @property
    def coherent(self) -> bool:
        return self.coherence >= self.theta

    @property
    def urgent(self) -> bool:
        return self.urgency >= self.brake


def coalition_energy(field_: Field, group: list[int]) -> float:
    """Σ_{i<j∈K} w_ij · a_i · a_j / |K|, normalized to 0..1 by its maximum (all weights and activations 1)."""
    n = len(group)
    if n < 2:
        return 0.0
    total = sum(field_.weight(i, j) * field_.a[i] * field_.a[j] for x, i in enumerate(group) for j in group[x + 1:])
    return float(total / n / ((n - 1) / 2))


class Gate:
    def __init__(self, window_steps: int):
        self.u = 0.0
        self.history: deque = deque(maxlen=max(1, window_steps))   # coalitions of the last 15 min (node ids)
        self.last_near: dict[str, float] = {}

    def stability(self, current: frozenset) -> float:
        if not self.history:
            return 0.0
        return sum(jaccard(current, past) for past in self.history) / len(self.history)

    @staticmethod
    def brake(fatigue: float, S: float, mode: str) -> float:
        factor = K.BRAKE_MODE.get(mode)
        return float("inf") if factor is None else K.BRAKE_B0 * (1 + K.FATIGUE_BRAKE_GAIN * fatigue) * (1 + S) * factor

    @staticmethod
    def theta(boredom: float, mode: str) -> float:
        return K.COHERENCE_THETA * (1 - K.COHERENCE_BOREDOM * boredom) * (K.REM_THETA_GAIN if mode == "rem" else 1)

    def step(self, dt: float, field_: Field, coalition: list[int], sources: dict[str, float], count_ok: bool,
             fatigue: float, S: float, boredom: float, mode: str) -> Reading:
        ids = frozenset(int(field_.ids[i]) for i in coalition)
        energy = coalition_energy(field_, coalition)
        stability = self.stability(ids)
        self.history.append(ids)
        above = {s: v for s, v in sources.items() if v >= K.URGENCY_FLOORS[s]}
        drive = sum(K.URGENCY_WEIGHTS[s] * v for s, v in above.items()) if count_ok else 0.0
        self.u += dt * (-self.u / K.URGENCY_TAU + drive)
        return Reading(coherence=energy * stability, energy=energy, stability=stability, theta=self.theta(boredom, mode),
                       urgency=self.u, brake=self.brake(fatigue, S, mode), sources=sources, counted=count_ok)

    @staticmethod
    def kinds_ok(sources: dict[str, float]) -> bool:
        return sum(1 for s, v in sources.items() if v >= K.URGENCY_FLOORS[s]) >= K.URGENCY_MIN_KINDS

    def near_miss(self, r: Reading, t: float) -> str | None:
        """'yawn' (coherent, not urgent) or 'worry' (urgent, not coherent), at most every 30 min per kind."""
        if r.brake == float("inf"):
            return None
        kind = "yawn" if r.coherent and not r.urgent else "worry" if r.urgent and not r.coherent else None
        if kind is None or t - self.last_near.get(kind, -1e18) < K.NEAR_MISS_MIN_GAP:
            return None
        self.last_near[kind] = t
        return kind

    def reset(self) -> None:
        self.u = 0.0
