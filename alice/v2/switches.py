"""Per-mechanism switches. Off for a whole run = build-time ablation (the mechanism never existed);
off on a probe fork = probe-time ablation (it existed, then was removed). All off = V1."""

from dataclasses import asdict, dataclass, replace

NAMES = ("lessons", "selfmodel", "intentions")


@dataclass(frozen=True)
class Switches:
    lessons: bool = True
    selfmodel: bool = True
    intentions: bool = True

    @classmethod
    def parse(cls, text: str | None) -> "Switches":
        """'all' (default), 'none', or a comma list of the mechanisms that are on."""
        text = (text or "all").strip().lower()
        if text == "all":
            return cls()
        if text == "none":
            return cls.none()
        on = {t.strip() for t in text.split(",") if t.strip()}
        if unknown := on - set(NAMES):
            raise ValueError(f"unknown V2 switch(es): {', '.join(sorted(unknown))}; choose from {', '.join(NAMES)}")
        return cls(**{n: n in on for n in NAMES})

    @classmethod
    def none(cls) -> "Switches":
        return cls(**{n: False for n in NAMES})

    def with_(self, changes: dict[str, bool]) -> "Switches":
        if unknown := set(changes) - set(NAMES):
            raise ValueError(f"unknown V2 switch(es): {', '.join(sorted(unknown))}")
        return replace(self, **{k: bool(v) for k, v in changes.items()})

    def as_dict(self) -> dict[str, bool]:
        return asdict(self)

    def __str__(self) -> str:
        on = [n for n in NAMES if getattr(self, n)]
        return ",".join(on) if on else "none"
