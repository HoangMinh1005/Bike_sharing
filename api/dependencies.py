from datetime import date, datetime
from typing import Dict, Optional, Set, Tuple

import pendulum
from fastapi import HTTPException, Query, status

ALLOWED_HEALTH_STATUSES: Set[str] = {"HEALTHY", "WARNING", "FAILED", "STALE", "UNKNOWN"}
ALLOWED_DEMAND_CATEGORIES: Set[str] = {"HIGH", "MEDIUM", "LOW"}


def _raise_bad_request(message: str) -> None:
    """Raise standardized HTTP 400 error."""
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "code": "BAD_REQUEST",
            "message": message,
        },
    )


def validate_date_param(date_str: str, param_name: str = "date") -> str:
    """
    Validate ISO date string format: YYYY-MM-DD.

    Returns:
        Formatted ISO date string: YYYY-MM-DD.
    Raises:
        HTTPException 400 if invalid.
    """
    if not date_str or not str(date_str).strip():
        _raise_bad_request(f"Query parameter '{param_name}' is required.")

    raw_value = str(date_str).strip()

    try:
        parsed_date = date.fromisoformat(raw_value)
    except ValueError:
        _raise_bad_request(
            f"Invalid date format for '{param_name}': '{date_str}'. Expected YYYY-MM-DD."
        )

    return parsed_date.isoformat()


def validate_date_range(
    start_date: str,
    end_date: str,
    max_days: int = 90,
) -> Tuple[str, str]:
    """
    Validate date range parameters (start_date <= end_date and range <= max_days).

    Returns:
        Tuple of formatted ISO date strings: (start_date, end_date)
    Raises:
        HTTPException 400 if range is invalid.
    """
    if max_days <= 0:
        _raise_bad_request("max_days must be greater than 0.")

    valid_start = validate_date_param(start_date, "start_date")
    valid_end = validate_date_param(end_date, "end_date")

    start_dt = date.fromisoformat(valid_start)
    end_dt = date.fromisoformat(valid_end)

    if start_dt > end_dt:
        _raise_bad_request(
            f"start_date ('{valid_start}') cannot be greater than end_date ('{valid_end}')."
        )

    days_diff = (end_dt - start_dt).days

    if days_diff > max_days:
        _raise_bad_request(
            f"Date range ({days_diff} days) exceeds maximum allowed limit of {max_days} days."
        )

    return valid_start, valid_end


def validate_datetime_param(dt_str: str, param_name: str = "time") -> str:
    """
    Validate ISO datetime timestamp parameter format.

    Returns:
        ISO formatted string.
    Raises:
        HTTPException 400 if invalid.
    """
    if not dt_str or not str(dt_str).strip():
        _raise_bad_request(f"Query parameter '{param_name}' is required.")

    raw_value = str(dt_str).strip()
    try:
        parsed = pendulum.parse(raw_value)
        return parsed.to_iso8601_string()
    except Exception:
        _raise_bad_request(
            f"Invalid ISO datetime format for '{param_name}': '{dt_str}'. "
            f"Expected YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS."
        )


def validate_datetime_range(
    start_time: Optional[str],
    end_time: Optional[str],
    max_days: int = 90,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Validate optional or required datetime range parameters (start_time <= end_time).

    Returns:
        Tuple of formatted ISO datetime strings or Nones.
    Raises:
        HTTPException 400 if range is invalid.
    """
    valid_start = validate_datetime_param(start_time, "start_time") if start_time else None
    valid_end = validate_datetime_param(end_time, "end_time") if end_time else None

    if valid_start and valid_end:
        start_dt = pendulum.parse(valid_start)
        end_dt = pendulum.parse(valid_end)

        if start_dt > end_dt:
            _raise_bad_request(
                f"start_time ('{start_time}') cannot be greater than end_time ('{end_time}')."
            )

        days_diff = (end_dt - start_dt).days
        if days_diff > max_days:
            _raise_bad_request(
                f"Datetime range ({days_diff} days) exceeds maximum allowed limit of {max_days} days."
            )

    return valid_start, valid_end


def validate_health_status(health_status: str) -> str:
    """
    Validate health_status query/path parameter against whitelist.

    Allowed: HEALTHY, WARNING, FAILED, STALE, UNKNOWN.
    """
    if not health_status or not str(health_status).strip():
        _raise_bad_request("health_status parameter is required.")

    val = str(health_status).strip().upper()
    if val not in ALLOWED_HEALTH_STATUSES:
        allowed_list = ", ".join(sorted(ALLOWED_HEALTH_STATUSES))
        _raise_bad_request(
            f"Invalid health_status '{health_status}'. Allowed values: [{allowed_list}]."
        )
    return val


def validate_demand_category(demand_category: Optional[str]) -> Optional[str]:
    """
    Validate demand_category parameter against whitelist.

    Allowed: HIGH, MEDIUM, LOW.
    """
    if demand_category is None or not str(demand_category).strip():
        return None

    val = str(demand_category).strip().upper()
    if val not in ALLOWED_DEMAND_CATEGORIES:
        allowed_list = ", ".join(sorted(ALLOWED_DEMAND_CATEGORIES))
        _raise_bad_request(
            f"Invalid demand_category '{demand_category}'. Allowed values: [{allowed_list}]."
        )
    return val


def pagination_params(
    limit: int = Query(
        50,
        ge=1,
        le=500,
        description="Number of records to return (1-500)",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Number of records to skip",
    ),
) -> Tuple[int, int]:
    """FastAPI dependency for pagination parameters."""
    return limit, offset


def validate_sort_params(
    sort_by: Optional[str],
    sort_order: str,
    allowed_fields: Dict[str, str],
) -> Tuple[Optional[str], str]:
    """Validate and map sort parameters."""
    order_clean = str(sort_order or "").strip().lower()

    if order_clean not in ("asc", "desc"):
        _raise_bad_request(
            f"Invalid sort_order '{sort_order}'. Must be 'asc' or 'desc'."
        )

    if sort_by is None or not str(sort_by).strip():
        return None, order_clean.upper()

    sort_clean = str(sort_by).strip().lower()

    if sort_clean not in allowed_fields:
        allowed_list = ", ".join(sorted(allowed_fields.keys()))
        _raise_bad_request(
            f"Invalid sort_by field '{sort_by}'. Allowed fields: [{allowed_list}]."
        )

    return allowed_fields[sort_clean], order_clean.upper()