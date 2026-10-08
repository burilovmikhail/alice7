"""When things happen in silence: modes and the sim-time schedule (no model, no state of its own)."""

from datetime import datetime, timedelta

from .config import V3Config

CONVERSATION, IDLE, ASLEEP = "conversation", "idle", "asleep"


def awake(t: datetime, cfg: V3Config) -> bool:
    return cfg.awake_from <= t.time() < cfg.awake_to


def mode(t: datetime, cfg: V3Config, session_open: bool) -> str:
    """conversation while a session is open; asleep outside the awake window; idle otherwise."""
    if session_open:
        return CONVERSATION
    return IDLE if awake(t, cfg) else ASLEEP


def stream_period(m: str, cfg: V3Config) -> timedelta:
    return timedelta(minutes=cfg.stream_asleep_min if m == ASLEEP else cfg.stream_idle_min)


def next_sleep(after: datetime, cfg: V3Config) -> datetime:
    """The first nightly sleep time strictly after `after`."""
    at = after.replace(hour=cfg.sleep_at.hour, minute=cfg.sleep_at.minute, second=0, microsecond=0)
    return at if at > after else at + timedelta(days=1)

