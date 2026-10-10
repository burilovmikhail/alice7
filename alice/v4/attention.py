"""Attention with inertia and lateral inhibition; working memory; coalitions (spec §6.4, T28–T30).

Working memory is the 7 most active nodes above 0.35: what is "on the agent's mind". The coalition is the largest
connected group in it. Focus grows while the same coalition dominates and decays when its energy drops; a new
coalition takes over only if its energy exceeds the current one's × (1 + focus). Nodes outside the focus coalition
are inhibited in proportion to focus, so when focus falls, what was held down comes up (the shower, T30).
"""

import numpy as np

from . import constants as K
from .field import Field


def jaccard(a, b) -> float:
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if a or b else 1.0


class Attention:
    def __init__(self):
        self.focus = 0.0
        self.focus_set: list[int] = []   # positions of the coalition attention is on
        self.wm: list[int] = []

    def working_memory(self, field: Field, a: np.ndarray | None = None) -> list[int]:
        a = field.a if a is None else a
        if not len(field):
            return []
        eligible = np.where(field.alive & np.array([k != "self" for k in field.kind]), a, 0.0)
        top = np.argsort(-eligible)[:K.WM_SIZE]
        return [int(i) for i in top if eligible[i] > K.WM_THRESHOLD]

    @staticmethod
    def coalition(field: Field, wm: list[int], a: np.ndarray | None = None) -> list[int]:
        """The largest connected group in working memory over edges ≥ 0.15 (ties: the more active)."""
        a = field.a if a is None else a
        left, groups = set(wm), []
        while left:
            stack, group = [left.pop()], []
            while stack:
                i = stack.pop()
                group.append(i)
                for j in list(left):
                    if field.weight(i, j) >= K.COALITION_EDGE:
                        left.discard(j)
                        stack.append(j)
            groups.append(sorted(group))
        if not groups:
            return []
        return max(groups, key=lambda g: (len(g), sum(a[i] for i in g)))

    @staticmethod
    def energy(field: Field, group: list[int]) -> float:
        return float(sum(field.a[i] for i in group if field.alive[i]))

    def update(self, field: Field, dt: float, arousal: float) -> bool:
        """One step. Returns True if attention switched to another coalition."""
        self.wm = self.working_memory(field)
        current = self.coalition(field, self.wm)
        focus_alive = [i for i in self.focus_set if i < len(field) and field.alive[i]]
        if not focus_alive:
            self.focus_set, self.focus = current, 0.0
            return bool(current)
        if current and jaccard(current, focus_alive) >= K.FOCUS_SAME:
            self.focus_set = current
            self.focus += (1 - self.focus) * dt / K.FOCUS_DWELL_TAU
            return False
        if current and self.energy(field, current) > self.energy(field, focus_alive) * (1 + self.focus):
            self.focus_set, self.focus = current, 0.0
            return True
        self.focus_set = focus_alive   # held by inertia, while its energy lasts
        self.focus -= self.focus * dt * (1 + arousal) / K.FOCUS_DECAY_TAU
        if self.energy(field, focus_alive) < K.WM_THRESHOLD:
            self.focus_set, self.focus = current, 0.0
            return bool(current)
        return False

    def outside_focus(self, field: Field) -> np.ndarray:
        out = np.ones(len(field))
        if self.focus_set:
            out[self.focus_set] = 0.0
        return out
