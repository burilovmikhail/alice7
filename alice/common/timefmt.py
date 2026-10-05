"""Human time phrases for prompts: "3 hours ago", "yesterday evening", "2 weeks ago"."""

from datetime import datetime


def _n(n: int, unit: str) -> str:
    return f"{n} {unit}" + ("" if n == 1 else "s")


def part_of_day(hour: int) -> str:
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 18:
        return "afternoon"
    if 18 <= hour < 23:
        return "evening"
    return "night"


def duration(seconds: float) -> str:
    minutes = int(seconds // 60)
    if minutes < 60:
        return _n(max(minutes, 1), "minute")
    hours = minutes // 60
    if hours < 48:
        return _n(hours, "hour")
    return _n(hours // 24, "day")


def ago(ts: str | datetime, now: datetime) -> str:
    t = datetime.fromisoformat(ts) if isinstance(ts, str) else ts
    seconds = (now - t).total_seconds()
    days = (now.date() - t.date()).days
    if seconds < 90:
        return "just now"
    if seconds < 6 * 3600:
        return f"{duration(seconds)} ago"
    if days == 0:
        return f"today ({part_of_day(t.hour)})"
    if days == 1:
        return f"yesterday ({part_of_day(t.hour)})"
    if days < 7:
        return f"{days} days ago"
    if days < 30:
        return f"{_n(days // 7, 'week')} ago"
    if days < 365:
        return f"{_n(days // 30, 'month')} ago"
    return f"{_n(days // 365, 'year')} ago"
