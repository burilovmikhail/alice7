"""Time source. Everything that ends up in memory takes its time from a Clock, never from datetime.now()."""

import re
from datetime import datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class RealClock:
    def now(self) -> datetime:
        return datetime.now().replace(microsecond=0)


class SimClock:
    """Settable, advanceable clock for experiments and replay."""

    def __init__(self, start: datetime):
        self._now = start.replace(microsecond=0)

    def now(self) -> datetime:
        return self._now

    def set(self, t: datetime) -> None:
        self._now = t.replace(microsecond=0)

    def advance(self, delta: timedelta) -> None:
        self._now += delta


def wall_now() -> datetime:
    """Wall-clock time for instrumentation only (trace `ts`), never for memory."""
    return datetime.now()


def iso(t: datetime) -> str:
    return t.isoformat(timespec="seconds")


def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s)


_PART = re.compile(r"(\d+(?:\.\d+)?)\s*(w|d|h|m|s)")
_UNITS = {"w": "weeks", "d": "days", "h": "hours", "m": "minutes", "s": "seconds"}


def parse_offset(value) -> timedelta:
    """'+2d', '1d12h', '+30m', '0', 2 (days) -> timedelta."""
    if isinstance(value, (int, float)):
        return timedelta(days=value)
    s = str(value).strip().lower().lstrip("+")
    if s in ("", "0"):
        return timedelta()
    parts = _PART.findall(s)
    if not parts or _PART.sub("", s).strip():
        raise ValueError(f"bad time offset: {value!r} (use e.g. +2d, +3h, +1d12h, +30m)")
    return sum((timedelta(**{_UNITS[u]: float(n)}) for n, u in parts), timedelta())
