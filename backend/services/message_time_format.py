"""
Human-readable message timestamps for chat API and AI context strings.

Rules (UTC calendar for API field ``time_display``; clients should format
``created_at`` in the user's timezone for UI):
- Under 1 minute: "Just now"
- 1, 2, or 5 minutes: "1 minute ago", "2 minutes ago", "5 minutes ago"
- 3–30 minutes (other values): "N minutes ago"
- Same calendar day, over 30 minutes: time · weekday, month day, year
- Yesterday: Yesterday · time · weekday, month day, year
- Two or more days ago: month day, year (no time)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


def _coerce_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        s = value.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return None


def _format_time_12h(dt: datetime) -> str:
    h = dt.hour % 12
    if h == 0:
        h = 12
    ap = "AM" if dt.hour < 12 else "PM"
    return f"{h}:{dt.strftime('%M')} {ap}"


def format_message_time(created_at: Any, now: Any = None) -> str:
    """
    Format a message ``created_at`` value relative to ``now`` (default: current UTC).
    Naive datetimes and naive ISO strings are interpreted as UTC.
    """
    then = _coerce_datetime(created_at)
    if then is None:
        return "Unknown time"

    if now is None:
        now_dt = datetime.now(timezone.utc)
    else:
        now_dt = _coerce_datetime(now)
        if now_dt is None:
            now_dt = datetime.now(timezone.utc)

    then = then.astimezone(timezone.utc)
    now_dt = now_dt.astimezone(timezone.utc)

    delta = now_dt - then
    secs = int(delta.total_seconds())
    if secs < 0:
        then_d = then.date()
        now_d = now_dt.date()
        day_diff = (now_d - then_d).days
        time_str = _format_time_12h(then)
        full_date_str = then.strftime("%A, %B %d, %Y")
        date_only_str = then.strftime("%B %d, %Y")
        if day_diff == 0:
            return f"{time_str} · {full_date_str}"
        if day_diff == 1:
            return f"Yesterday · {time_str} · {full_date_str}"
        return date_only_str

    if secs < 60:
        return "Just now"

    minutes = secs // 60
    if minutes <= 30:
        if minutes == 1:
            return "1 minute ago"
        if minutes == 2:
            return "2 minutes ago"
        if minutes == 5:
            return "5 minutes ago"
        return f"{minutes} minutes ago"

    then_d = then.date()
    now_d = now_dt.date()
    day_diff = (now_d - then_d).days

    time_str = _format_time_12h(then)
    full_date_str = then.strftime("%A, %B %d, %Y")
    date_only_str = then.strftime("%B %d, %Y")

    if day_diff == 0:
        return f"{time_str} · {full_date_str}"
    if day_diff == 1:
        return f"Yesterday · {time_str} · {full_date_str}"
    return date_only_str
