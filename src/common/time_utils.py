from datetime import datetime, timezone
from typing import Optional, Union

def utc_now() -> datetime:
    """
    Return the current timezone-aware datetime in UTC.
    """
    return datetime.now(timezone.utc)

def parse_unix_timestamp(value: Optional[Union[int, float, str]]) -> Optional[datetime]:
    """
    Parse a Unix timestamp (seconds or milliseconds) and return a UTC aware datetime.
    Returns None if the value is None or cannot be parsed.
    """
    if value is None:
        return None
    try:
        val = float(value)
        # Identify milliseconds timestamps (normally 13 digits, > 1e11) vs seconds (normally 10 digits)
        if val > 1e11:
            val = val / 1000.0
        return datetime.fromtimestamp(val, timezone.utc)
    except (ValueError, TypeError):
        return None

def safe_timestamp_from_gbfs(value: Optional[Union[int, float, str]]) -> Optional[datetime]:
    """
    Safely convert a timestamp value from GBFS feeds into a UTC aware datetime.
    Returns None if the value is None or fails to parse.
    """
    return parse_unix_timestamp(value)
