"""Sleep as a mode of the same dynamics (spec §6.10, T66–T75). No awake window, no clock time for sleep.

- onset, outside a conversation, per step: p = dt · k · sigmoid((S − C − θ − 0.5·arousal − 0.5·u) / T). A boring
  evening tips over early; an open intention or strong urgency keeps the agent up;
- 90-minute cycles, NREM then REM, REM growing longer toward morning;
- NREM: input, spreading and noise turned down; the day's nodes replayed in the order they came, sampled by
  salience; Hebbian learning ×3; weak edges fade faster; near-duplicates pool. The narrative review and the
  dissonance check run once, at the end of the first NREM (in the agent: they call models);
- REM: less inhibition, more noise, weak edges count double; the gate runs with a higher coherence threshold and a
  firing is a dream, at most two a night;
- waking when sleep pressure is low and the circadian phase rising, or on strong input. A user message always wakes
  the agent (D10).
"""

import math

import numpy as np

from . import constants as K
from .drives import circadian, circadian_rising
from .field import Field, at_minute

AWAKE, NREM, REM = "awake", "nrem", "rem"


def onset_probability(dt: float, S: float, C: float, arousal: float, u_norm: float) -> float:
    z = (S - C - K.SLEEP_THETA - 0.5 * arousal - K.SLEEP_URGENCY * u_norm) / K.SLEEP_T
    return dt * K.SLEEP_K / (1 + math.exp(-max(-60.0, min(60.0, z))))


def rem_share(cycle: int) -> float:
    return min(K.REM_SHARE_MAX, K.REM_SHARE_FIRST + K.REM_SHARE_STEP * cycle)


class SleepCycle:
    def __init__(self):
        self.mode = AWAKE
        self.onset_at: float | None = None
        self.cycle = 0
        self.cycle_start = 0.0
        self.dreams = 0
        self.narrative_done = False
        self.replay: list[int] = []        # node ids, in the order they came
        self.last_replay = 0.0
        self.last_wake: float | None = None

    # ---------- persistence ----------

    def state(self) -> dict:
        return dict(self.__dict__)

    def restore(self, d: dict) -> None:
        self.__dict__.update(d)

    # ---------- transitions ----------

    def fall_asleep(self, field: Field, t: float, rng: np.random.Generator) -> None:
        self.mode, self.onset_at, self.cycle, self.cycle_start = NREM, t, 0, t
        self.dreams, self.narrative_done, self.last_replay = 0, False, t
        since = self.last_wake if self.last_wake is not None else t - 1440
        day = [i for i in np.argsort(field.created, kind="stable")
               if field.created[i] > since and field.alive[i] and field.kind[i] not in ("user", "self")]
        # the day's nodes in the order they came, sampled by salience
        self.replay = [int(field.ids[i]) for i in day if rng.random() < 0.3 + 0.7 * field.salience[i]]

    def wake(self, t: float) -> None:
        self.mode, self.last_wake = AWAKE, t

    def phase(self, t: float) -> str | None:
        """Advance the NREM/REM cycle. Returns 'rem' or 'nrem' when the stage changes."""
        if self.mode == AWAKE:
            return None
        nrem_len = K.CYCLE_MIN * (1 - rem_share(self.cycle))
        if self.mode == NREM and t - self.cycle_start >= nrem_len:
            self.mode = REM
            return REM
        if self.mode == REM and t - self.cycle_start >= K.CYCLE_MIN:
            self.cycle += 1
            self.cycle_start = t
            self.mode = NREM
            return NREM
        return None

    def should_wake(self, t: float, S: float) -> bool:
        return self.mode != AWAKE and S < K.WAKE_S and circadian_rising(at_minute(t).hour + at_minute(t).minute / 60)

    def next_replay(self, field: Field, t: float) -> int | None:
        """NREM: one of the day's nodes every few minutes (a position), or None."""
        if self.mode != NREM or t - self.last_replay < K.REPLAY_EVERY_MIN:
            return None
        self.last_replay = t
        while self.replay:
            i = field.index.get(self.replay.pop(0))
            if i is not None and field.alive[i]:
                return i
        return None


def hour_of(t: float) -> float:
    d = at_minute(t)
    return d.hour + d.minute / 60


def circadian_at(t: float) -> float:
    return circadian(hour_of(t))
