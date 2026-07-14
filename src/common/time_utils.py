from datetime import datetime, timezone
from typing import Optional, Union


TimestampValue = Optional[Union[int, float, str]]


def utc_now() -> datetime:
    """
    Return the current timezone-aware datetime in UTC.
    """
    return datetime.now(timezone.utc)


def parse_unix_timestamp(value: TimestampValue) -> Optional[datetime]:
    """
    Parse a Unix timestamp in seconds or milliseconds
    and return a timezone-aware UTC datetime.

    Returns None if the value is None or cannot be parsed.
    """
    if value is None:
        return None

    try:
        timestamp_value = float(value)

        # Millisecond timestamps are usually 13 digits.
        # Second timestamps are usually 10 digits.
        if timestamp_value > 1e11:
            timestamp_value = timestamp_value / 1000.0

        return datetime.fromtimestamp(timestamp_value, timezone.utc)

    except (ValueError, TypeError, OverflowError, OSError):
        return None


def safe_timestamp_from_gbfs(value: TimestampValue) -> Optional[datetime]:
    """
    Convert a GBFS timestamp value into a timezone-aware UTC datetime.
    """
    return parse_unix_timestamp(value)