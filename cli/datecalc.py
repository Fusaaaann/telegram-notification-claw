from __future__ import annotations

import re
from datetime import date, datetime, timedelta


def parse_iso_datetime_loose(s: str) -> datetime:
    """Parse a loose ISO datetime string.

    Accepts:
    - YYYY-MM-DD
    - YYYY-MM-DDTHH:MM
    - YYYY-MM-DDTHH:MM:SS

    If only date is provided, defaults to 09:00:00.
    """
    s = s.strip()
    if "T" not in s:
        d = date.fromisoformat(s)
        return datetime(d.year, d.month, d.day, 9, 0, 0)
    if s.endswith("Z"):
        s = s[:-1]
    return datetime.fromisoformat(s)


def to_iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def parse_due_at(s: str) -> datetime:
    """Parse an absolute or relative due-at expression.

    Absolute:
    - YYYY-MM-DD
    - YYYY-MM-DDTHH:MM[:SS]

    Relative:
    - now
    - today (09:00)
    - tomorrow (09:00)
    - +Nd, +Nh, +Nm, +Nw  (e.g. +3d, +2h, +30m, +1w)

    Notes:
    - Relative offsets are applied from current local time.
    """
    s = s.strip().lower()
    if not s:
        raise ValueError("empty")

    now = datetime.now().replace(microsecond=0)

    if s == "now":
        return now
    if s == "today":
        d = date.today()
        return datetime(d.year, d.month, d.day, 9, 0, 0)
    if s == "tomorrow":
        d = date.today() + timedelta(days=1)
        return datetime(d.year, d.month, d.day, 9, 0, 0)

    m = re.fullmatch(r"\+(\d+)([dhmw])", s)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        if unit == "m":
            return now + timedelta(minutes=n)
        if unit == "h":
            return now + timedelta(hours=n)
        if unit == "d":
            return now + timedelta(days=n)
        if unit == "w":
            return now + timedelta(weeks=n)

    # fallback: absolute ISO
    return parse_iso_datetime_loose(s)
