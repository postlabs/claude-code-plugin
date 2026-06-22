"""Datetime + JSON helpers shared across kits."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def utc_now() -> datetime:
    """Current UTC time as a timezone-aware ``datetime``."""
    return datetime.now(timezone.utc)


def parse_datetime(value: str | None) -> datetime | None:
    """Parse an ISO 8601 datetime string into a UTC-aware ``datetime``.

    Accepts ``Z`` suffix, ``+00:00`` offsets, naive ``YYYY-MM-DD[ T]HH:MM:SS``
    forms, and bare ``YYYY-MM-DD`` (treated as UTC midnight). Returns
    ``None`` for empty / unparseable input.
    """
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is not None:
            return dt.astimezone(timezone.utc)
        return dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def format_datetime(dt: datetime | None) -> str | None:
    """Format a ``datetime`` to ISO 8601 with millisecond precision and
    a trailing ``Z`` (UTC). Returns ``None`` if input is ``None``."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    else:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def to_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


__all__ = [
    "now_iso",
    "utc_now",
    "parse_datetime",
    "format_datetime",
    "to_json",
]
