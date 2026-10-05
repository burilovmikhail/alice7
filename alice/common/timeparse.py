"""Relative dates in a query ("yesterday", "last week", «вчера», «во вторник») -> (first day, last day)."""

import re
from datetime import date, timedelta

_DAYS_AGO = re.compile(r"(\d+)\s+(?:дн|день|day)\w*\s+(?:назад|ago)")
_WEEKS_AGO = re.compile(r"(?:(\d+)\s+)?(?:недел\w*|weeks?)\s+(?:назад|ago)")

# Weekday stems; Russian accusative forms («в среду», «в пятницу») share them
_WEEKDAYS = [
    ("monday", "понедельник"), ("tuesday", "вторник"), ("wednesday", "сред"), ("thursday", "четверг"),
    ("friday", "пятниц"), ("saturday", "суббот"), ("sunday", "воскресень"),
]
_RU_WEEKDAY_CONTEXT = re.compile(r"\b(?:в|во|прошл\w*)\s+(понедельник|вторник|сред\w*|четверг|пятниц\w*|суббот\w*|воскресень\w*)")


def _last_weekday(today: date, weekday: int) -> date:
    """Most recent such weekday strictly before today."""
    delta = (today.weekday() - weekday) % 7 or 7
    return today - timedelta(days=delta)


def parse_time_range(text: str, today: date) -> tuple[date, date] | None:
    t = text.lower()

    if "позавчера" in t or "day before yesterday" in t:
        d = today - timedelta(days=2)
        return d, d
    if "вчера" in t or "yesterday" in t:
        d = today - timedelta(days=1)
        return d, d
    if m := _DAYS_AGO.search(t):
        d = today - timedelta(days=int(m.group(1)))
        return d, d
    if "a day ago" in t:
        d = today - timedelta(days=1)
        return d, d
    if m := _WEEKS_AGO.search(t):
        d = today - timedelta(weeks=int(m.group(1) or 1))
        return d - timedelta(days=3), d + timedelta(days=3)
    if "прошлой неделе" in t or "last week" in t:
        monday = today - timedelta(days=today.weekday() + 7)
        return monday, monday + timedelta(days=6)
    if "этой неделе" in t or "this week" in t:
        return today - timedelta(days=today.weekday()), today
    if "прошлом месяце" in t or "last month" in t:
        last_prev = today.replace(day=1) - timedelta(days=1)
        return last_prev.replace(day=1), last_prev
    for i, (en, _) in enumerate(_WEEKDAYS):
        if re.search(rf"\b{en}\b", t):
            d = _last_weekday(today, i)
            return d, d
    if m := _RU_WEEKDAY_CONTEXT.search(t):
        word = m.group(1)
        i = next(i for i, (_, ru) in enumerate(_WEEKDAYS) if word.startswith(ru))
        d = _last_weekday(today, i)
        return d, d
    if "сегодня" in t or "утром" in t or "today" in t or "this morning" in t:
        return today, today
    if "недавно" in t or "последнее время" in t or "recently" in t or "lately" in t:
        return today - timedelta(days=7), today
    return None
