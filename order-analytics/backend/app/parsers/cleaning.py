"""Small, reusable helpers for type conversion and handling missing / inconsistent values."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

_MISSING = {"", "na", "n/a", "null", "none", "nan", "-"}

_DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d", "%d %b %Y", "%Y-%m-%dT%H:%M:%S")

# Normalise free-text shipment statuses to a small, known vocabulary.
_STATUS_MAP = {
    "delivered": "Delivered", "complete": "Delivered", "completed": "Delivered",
    "delayed": "Delayed", "late": "Delayed",
    "in transit": "In Transit", "in_transit": "In Transit", "shipped": "In Transit",
    "pending": "Pending", "processing": "Pending",
    "cancelled": "Cancelled", "canceled": "Cancelled",
}


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and value != value:  # NaN
        return True
    return isinstance(value, str) and value.strip().lower() in _MISSING


def clean_str(value: Any, upper: bool = False) -> str | None:
    if is_missing(value):
        return None
    s = str(value).strip()
    return s.upper() if upper else s


def clean_id(value: Any) -> str | None:
    """IDs are compared case-insensitively and may arrive as ints ('1001' vs 1001 vs 1001.0)."""
    if is_missing(value):
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip().upper()


def to_int(value: Any, default: int | None = None) -> int | None:
    if is_missing(value):
        return default
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return default


def to_float(value: Any, default: float | None = None) -> float | None:
    if is_missing(value):
        return default
    try:
        cleaned = str(value).replace(",", "").replace("₹", "").replace("$", "").strip()
        return float(cleaned)
    except (TypeError, ValueError):
        return default


def to_date(value: Any) -> date | None:
    if is_missing(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def normalize_status(value: Any) -> str | None:
    s = clean_str(value)
    if s is None:
        return None
    return _STATUS_MAP.get(s.lower(), s.title())
