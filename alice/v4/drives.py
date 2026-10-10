"""The drive system (spec §6.3): eleven coupled variables with their own time constants, saturation and noise.

Each drive follows dx/dt = (x₀ − x)/τ + inputs + Σ_y W_xy · y + σ·ξ, clamped to 0..1 (valence and mood −1..1).
Valence has two layers, as V3's affect: a fast one that relaxes to the mood within minutes, and the mood, which
relaxes to the temperament over days. Circadian phase is an input, not a drive. Drives switched off (or outside the
minimal set) stay at their baselines. They reach a prompt only in words, and only when far from baseline (D7).
"""

import math
from dataclasses import dataclass

import numpy as np

from ..common.timefmt import duration
from ..v3.affect import tone
from . import constants as K

NAMES = tuple(K.DRIVE_BASE)
SIGNED = ("valence", "mood")
NOISY = ("arousal", "valence", "curiosity", "boredom", "social")   # not those that rest at 0: noise would push them up


def circadian(hour: float) -> float:
    """0..1, peak at 17:00, trough at 05:00."""
    return 0.5 + 0.5 * math.cos(2 * math.pi * (hour - K.CIRCADIAN_PEAK_H) / 24)


def circadian_rising(hour: float) -> bool:
    trough = (K.CIRCADIAN_PEAK_H + 12) % 24
    return (hour - trough) % 24 < 12


@dataclass
class Context:
    """What the drives see of the rest of the system at one step."""
    asleep: bool = False
    conversation: bool = False
    novelty: float = 0.0          # recent novelty of input, 0..1
    activity: float = 0.0         # how active the field is (mean of working memory), 0..1
    conflict: float = 0.0         # opposite-signal traces active together, 0..1
    goal: float = 0.0             # Σ unfinishedness × proximity to due, squashed
    open_questions: int = 0
    unanswered: bool = False      # a message written first has had no reply for a while
    engagement: float = 0.0       # the last reaction's positive signal


class Drives:
    def __init__(self, active: set[str] | None = None):
        self.x = dict(K.DRIVE_BASE)
        self.active = set(NAMES) if active is None else set(active)

    def get(self, name: str) -> float:
        return self.x[name]

    def pulse(self, name: str, delta: float) -> None:
        if name in self.active:
            self._set(name, self.x[name] + delta)

    def set(self, name: str, value: float) -> None:
        if name in self.active:
            self._set(name, value)

    def _set(self, name: str, value: float) -> None:
        lo = -1.0 if name in SIGNED else 0.0
        self.x[name] = float(min(1.0, max(lo, value)))

    def step(self, dt: float, ctx: Context, rng: np.random.Generator | None) -> None:
        x, base = self.x, K.DRIVE_BASE
        d = dict.fromkeys(NAMES, 0.0)
        d["S"] = -x["S"] / (K.S_FALL_TAU_H * 60) if ctx.asleep else (1 - x["S"]) / (K.S_RISE_TAU_H * 60)
        d["arousal"] = ((K.AROUSAL_ASLEEP if ctx.asleep else base["arousal"]) - x["arousal"]) / K.AROUSAL_TAU
        d["valence"] = (x["mood"] - x["valence"]) * math.log(2) / K.VALENCE_HALF_MIN
        d["mood"] = (base["mood"] - x["mood"]) * math.log(2) / (K.MOOD_HALF_DAYS * 1440)
        d["fatigue"] = -x["fatigue"] / K.FATIGUE_TAU
        d["curiosity"] = (base["curiosity"] - x["curiosity"]) / K.CURIOSITY_TAU \
            + K.CURIOSITY_PER_QUESTION * ctx.open_questions
        idle = not ctx.asleep and not ctx.conversation
        target = max(base["boredom"], 1 - (ctx.novelty + ctx.activity) / 2) if idle else base["boredom"]
        d["boredom"] = (target - x["boredom"]) / K.BOREDOM_RISE_MIN
        if ctx.conversation:
            d["social"] = (base["social"] - x["social"]) / K.SOCIAL_CONVERSATION_TAU * (1 + max(0.0, ctx.engagement))
        elif not ctx.asleep:
            d["social"] = (1 - x["social"]) / K.SOCIAL_SATURATE_MIN
        d["uncertainty"] = (ctx.conflict - x["uncertainty"]) / K.UNCERTAINTY_TAU
        d["frustration"] = -x["frustration"] / K.FRUSTRATION_TAU + (K.FRUSTRATION_UNANSWERED if ctx.unanswered else 0)
        d["dissonance"] = -x["dissonance"] / K.DISSONANCE_TAU
        for target_name, row in K.COUPLING.items():
            d[target_name] += sum(w * x[src] for src, w in row.items())
        for name in NAMES:
            if name not in self.active:
                continue
            if name == "goal_tension":
                self._set(name, ctx.goal)
                continue
            value = x[name] + dt * d[name]
            if rng is not None and name in NOISY:
                value += K.DRIVE_NOISE * math.sqrt(dt) * rng.standard_normal()
            self._set(name, value)

    def appraisal(self, valence: float, mood: float, arousal: float) -> None:
        """V3's appraisal of an exchange (§4.3: appraisals write the substrate): the fast layer and the mood take
        V3 affect's values; arousal moves toward the appraisal's."""
        self.set("valence", valence)
        self.set("mood", mood)
        self.pulse("arousal", K.AROUSAL_APPRAISAL * max(0.0, arousal - self.x["arousal"]))

    def salient(self) -> dict[str, float]:
        """Drives far from their baselines (only these reach a prompt, in words)."""
        return {n: v for n, v in self.x.items()
                if n not in ("valence", "mood") and abs(v - K.DRIVE_BASE[n]) >= K.SALIENT_DRIVE}

    def words(self, silence_seconds: float | None, asleep: bool = False) -> str:
        """Mood and the salient drives in words; no number is ever shown (D7)."""
        x = self.x
        lines = [tone(x["valence"], x["arousal"])]
        s = self.salient()
        if "S" in s and x["S"] > 0.6 and not asleep:
            lines.append("you are getting sleepy")
        if "arousal" in s:
            lines.append("you feel keyed up" if x["arousal"] > K.DRIVE_BASE["arousal"] else "you feel slow and quiet")
        if "fatigue" in s:
            lines.append("you have been thinking a lot and are tired of it")
        if "social" in s and x["social"] > K.DRIVE_BASE["social"]:
            lines.append(f"you haven't talked to anyone for {duration(silence_seconds)}" if silence_seconds
                         else "you would like to talk to someone")
        if "curiosity" in s and x["curiosity"] > K.DRIVE_BASE["curiosity"]:
            lines.append("something open keeps you curious")
        if "boredom" in s:
            lines.append("you are a bit bored")
        if "uncertainty" in s:
            lines.append("something doesn't add up")
        if "goal_tension" in s:
            lines.append("something you meant to do is pressing")
        if "frustration" in s:
            lines.append("something has been frustrating you")
        if "dissonance" in s:
            lines.append("something about how you see yourself doesn't sit right")
        return "; ".join(lines)
