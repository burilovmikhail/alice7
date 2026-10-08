"""V3 switches, next to V2's three. Off for a run = build-time ablation; off on a fork = probe-time ablation.
All V3 switches off = V2."""

from dataclasses import asdict, dataclass, replace

NAMES = ("stream", "wakes", "sleep", "affect", "initiative")
TIME = ("stream", "wakes", "sleep")   # processes that run in silence


@dataclass(frozen=True)
class V3Switches:
    stream: bool = True
    wakes: bool = True
    sleep: bool = True
    affect: bool = True
    initiative: bool = True

    @classmethod
    def parse(cls, text: str | None) -> "V3Switches":
        text = (text or "all").strip().lower()
        if text == "all":
            return cls()
        if text == "none":
            return cls.none()
        on = {t.strip() for t in text.split(",") if t.strip()}
        if unknown := on - set(NAMES):
            raise ValueError(f"unknown V3 switch(es): {', '.join(sorted(unknown))}; choose from {', '.join(NAMES)}")
        return cls(**{n: n in on for n in NAMES})

    @classmethod
    def none(cls) -> "V3Switches":
        return cls(**{n: False for n in NAMES})

    def with_(self, changes: dict[str, bool]) -> "V3Switches":
        if unknown := set(changes) - set(NAMES):
            raise ValueError(f"unknown V3 switch(es): {', '.join(sorted(unknown))}")
        return replace(self, **{k: bool(v) for k, v in changes.items()})

    def as_dict(self) -> dict[str, bool]:
        return asdict(self)

    @property
    def lives_in_silence(self) -> bool:
        return any(getattr(self, n) for n in TIME)

    def __str__(self) -> str:
        on = [n for n in NAMES if getattr(self, n)]
        return ",".join(on) if on else "none"
