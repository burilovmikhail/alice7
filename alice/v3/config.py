"""V3 settings (kept here so the shared code and V2 stay free of V3 terms)."""

import os
from dataclasses import asdict, dataclass, field
from datetime import time

from ..common.config import Config
from .switches import V3Switches


def _hhmm(text: str) -> time:
    h, m = text.strip().split(":")
    return time(int(h), int(m))


@dataclass(frozen=True)
class V3Config:
    stream_model: str | None = None     # background thoughts; None = the fast model
    wake_model: str | None = None       # wakes and sleep; None = the chat model
    stream_idle_min: int = 60           # sim minutes between stream ticks in silence while awake
    stream_asleep_min: int = 180        # ... while asleep
    awake_from: time = time(8, 0)
    awake_to: time = time(23, 0)
    sleep_at: time = time(2, 0)         # the nightly sleep, if anything new happened since the last one
    wakes_per_day: int = 4
    writes_per_day: int = 1
    quiet_after_hours: int = 12         # no writing first this soon after a conversation, unless something is due
    switches: V3Switches = field(default_factory=V3Switches)

    def models(self, cfg: Config) -> dict[str, str]:
        return {"stream": self.stream_model or cfg.fast_model, "wake": self.wake_model or cfg.chat_model}

    def public(self, cfg: Config) -> dict:
        d = asdict(self)
        d["switches"] = self.switches.as_dict()
        for k in ("awake_from", "awake_to", "sleep_at"):
            d[k] = getattr(self, k).strftime("%H:%M")
        d.update({f"{k}_model": v for k, v in self.models(cfg).items()})
        return d


def load_v3_config() -> V3Config:
    def get(name: str) -> str | None:
        value = os.getenv(name)
        return value if value not in (None, "") else None

    awake = (get("ALICE_AWAKE") or "08:00-23:00").split("-")
    return V3Config(
        stream_model=get("ALICE_STREAM_MODEL"), wake_model=get("ALICE_WAKE_MODEL"),
        stream_idle_min=int(get("ALICE_STREAM_IDLE_MIN") or 60),
        stream_asleep_min=int(get("ALICE_STREAM_ASLEEP_MIN") or 180),
        awake_from=_hhmm(awake[0]), awake_to=_hhmm(awake[1]), sleep_at=_hhmm(get("ALICE_SLEEP_AT") or "02:00"),
        wakes_per_day=int(get("ALICE_WAKES_PER_DAY") or 4), writes_per_day=int(get("ALICE_WRITES_PER_DAY") or 1),
        quiet_after_hours=int(get("ALICE_QUIET_AFTER_HOURS") or 12),
        switches=V3Switches.parse(get("ALICE_V3_SWITCHES")))
