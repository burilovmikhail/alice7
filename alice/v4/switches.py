"""V4 switches, next to V2's and V3's (spec §5). Off for a run = build-time ablation; off on a fork = probe-time
ablation. All V4 switches off = V3; every other V4 switch requires `field`."""

from dataclasses import asdict, dataclass, replace

NAMES = ("field", "drives", "gate", "recall", "traces", "narrative", "sleep_mode", "intrusions", "reconsolidation")


@dataclass(frozen=True)
class V4Switches:
    field: bool = True
    drives: bool = True
    gate: bool = True
    recall: bool = True
    traces: bool = True
    narrative: bool = True
    sleep_mode: bool = True
    intrusions: bool = True
    reconsolidation: bool = True

    @classmethod
    def parse(cls, text: str | None) -> "V4Switches":
        text = (text or "all").strip().lower()
        if text == "all":
            return cls()
        if text == "none":
            return cls.none()
        on = {t.strip() for t in text.split(",") if t.strip()}
        if unknown := on - set(NAMES):
            raise ValueError(f"unknown V4 switch(es): {', '.join(sorted(unknown))}; choose from {', '.join(NAMES)}")
        return cls(**{n: n in on for n in NAMES})

    @classmethod
    def none(cls) -> "V4Switches":
        return cls(**{n: False for n in NAMES})

    def with_(self, changes: dict[str, bool]) -> "V4Switches":
        if unknown := set(changes) - set(NAMES):
            raise ValueError(f"unknown V4 switch(es): {', '.join(sorted(unknown))}")
        return replace(self, **{k: bool(v) for k, v in changes.items()})

    def on(self, name: str) -> bool:
        """A switch counts only with the field on."""
        return self.field and getattr(self, name)

    def as_dict(self) -> dict[str, bool]:
        return asdict(self)

    def __str__(self) -> str:
        on = [n for n in NAMES if getattr(self, n)]
        return ",".join(on) if on else "none"
