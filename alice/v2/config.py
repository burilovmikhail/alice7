"""V2 settings on top of the shared Config (kept here so the shared code stays free of V2 terms)."""

import os
from dataclasses import asdict, dataclass, field

from ..common.config import Config
from .switches import Switches


@dataclass(frozen=True)
class V2Config:
    reflect_model: str | None = None   # reflector and self-review; None = the chat model (spec D5)
    observe_model: str | None = None   # per-turn self-observation; None = the fast model
    lessons_budget: int = 400          # tokens for habits in the system prompt
    portrait_words: int = 180
    reflect_every: int = 6             # unreflected signals that trigger a mid-session reflection
    switches: Switches = field(default_factory=Switches)

    def models(self, cfg: Config) -> dict[str, str]:
        return {"reflect": self.reflect_model or cfg.chat_model, "observe": self.observe_model or cfg.fast_model}

    def public(self, cfg: Config) -> dict:
        d = asdict(self)
        d["switches"] = self.switches.as_dict()
        d.update({f"{k}_model": v for k, v in self.models(cfg).items()})
        return d


def load_v2_config() -> V2Config:
    """From the environment (call after load_config(), which reads .env)."""
    def get(name: str) -> str | None:
        value = os.getenv(name)
        return value if value not in (None, "") else None

    return V2Config(
        reflect_model=get("ALICE_REFLECT_MODEL"),
        observe_model=get("ALICE_OBSERVE_MODEL"),
        lessons_budget=int(get("ALICE_LESSONS_BUDGET") or 400),
        portrait_words=int(get("ALICE_PORTRAIT_WORDS") or 180),
        reflect_every=int(get("ALICE_REFLECT_EVERY") or 6),
        switches=Switches.parse(get("ALICE_V2_SWITCHES")),
    )
