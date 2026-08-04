from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Mapping, Optional, Tuple

import pendulum

from src.common.db import execute_sql
from src.common.logger import get_logger
from src.mart.daily_mart_builder import (
    build_daily_region_summary,
    build_daily_station_summary,
    build_daily_system_summary,
    build_station_demand_ranking,
)
from src.mart.hourly_mart_builder import (
    build_hourly_region_availability,
    build_hourly_station_availability,
    build_vehicle_type_availability_summary,
    build_weather_mobility_summary,
)
from src.quality.daily_mart_checks import run_daily_mart_dq_checks
from src.quality.hourly_mart_checks import run_hourly_mart_dq_checks

logger = get_logger(__name__)

VALID_BACKFILL_TYPES = {"hourly", "daily", "both"}

MAX_HOURLY_BACKFILL_DAYS = 31
MAX_DAILY_BACKFILL_DAYS = 366

DEFAULT_BUSINESS_TIMEZONE = "UTC"
DB_TIMESTAMP_FORMAT = "YYYY-MM-DD HH:mm:ss"


def _require_non_empty_string(value: Any, field_name: str) -> str:
    """
    Return a stripped non-empty string.

    Raises:
        ValueError if value is None or blank.
    """
    if value is None or not str(value).strip():
        raise ValueError(f"'{field_name}' must be a non-empty value.")

    return str(value).strip()


def _parse_datetime(
    value: Any,
    field_name: str,
    timezone_name: str = DEFAULT_BUSINESS_TIMEZONE,
) -> pendulum.DateTime:
    """
    Parse date/datetime input into a timezone-aware pendulum DateTime.

    Rules:
    - Date-only input like "2026-07-01" is interpreted as midnight.
    - Naive datetime is interpreted in timezone_name.
    - Aware datetime is converted to timezone_name.
    """
    raw_value = _require_non_empty_string(value, field_name)

    try:
        parsed = pendulum.parse(raw_value)
    except Exception as exc:
        raise ValueError(
            f"Invalid {field_name} value '{raw_value}'. "
            f"Expected ISO date/datetime string. Original error: {exc}"
        ) from exc

    if parsed.tzinfo is None:
        parsed = pendulum.datetime(
            parsed.year,
            parsed.month,
            parsed.day,
            parsed.hour,
            parsed.minute,
            parsed.second,
            parsed.microsecond,
            tz=timezone_name,
        )
    else:
        parsed = parsed.in_timezone(timezone_name)

    return parsed


def _floor_to_hour(value: pendulum.DateTime) -> pendulum.DateTime:
    """
    Floor datetime to the beginning of the hour.
    """
    return value.replace(
        minute=0,
        second=0,
        microsecond=0,
    )


def _ceil_to_hour(value: pendulum.DateTime) -> pendulum.DateTime:
    """
    Ceil datetime to the next hour if it is not already hour-aligned.
    """
    floored = _floor_to_hour(value)

    if value == floored:
        return value

    return floored.add(hours=1)


def _to_db_timestamp(value: pendulum.DateTime) -> str:
    """
    Convert pendulum DateTime to PostgreSQL-friendly timestamp string.
    """
    return value.in_timezone("UTC").format(DB_TIMESTAMP_FORMAT)


def _validate_backfill_type(backfill_type: Any) -> str:
    """
    Validate backfill_type.
    """
    value = _require_non_empty_string(backfill_type, "backfill_type").lower()

    if value not in VALID_BACKFILL_TYPES:
        raise ValueError(
            f"Invalid backfill_type '{value}'. "
            f"Allowed values: {sorted(VALID_BACKFILL_TYPES)}."
        )

    return value


def _validate_daily_range(
    start_date: str,
    end_date: str,
    max_days: int = MAX_DAILY_BACKFILL_DAYS,
) -> None:
    """
    Validate inclusive daily date range.
    """
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError as exc:
        raise ValueError(
            f"Invalid daily date range: start_date={start_date}, "
            f"end_date={end_date}. Expected YYYY-MM-DD."
        ) from exc

    if start > end:
        raise ValueError(
            f"Invalid daily backfill range: start_date '{start_date}' "
            f"cannot be greater than end_date '{end_date}'."
        )

    day_count = (end - start).days + 1

    if day_count > max_days:
        raise ValueError(
            f"Daily backfill range has {day_count} day(s), "
            f"which exceeds the maximum allowed limit of {max_days} day(s)."
        )


def parse_backfill_conf(
    conf: Mapping[str, Any],
    business_timezone: str = DEFAULT_BUSINESS_TIMEZONE,
) -> Dict[str, Any]:
    """
    Parse and validate backfill configuration.

    Supported backfill types:
    - hourly
    - daily
    - both

    Hourly convention:
        [start, end)
        end is exclusive.

    Daily convention:
        start_date and end_date are inclusive.

    For backfill_type="both":
    - hourly backfill uses [start, end)
    - daily backfill rebuilds dates affected by that hourly interval

    Example:
        {
          "backfill_type": "both",
          "start": "2026-07-01T00:00:00",
          "end": "2026-07-08T00:00:00"
        }

    Hourly windows:
        2026-07-01 00:00:00 <= hour < 2026-07-08 00:00:00

    Daily dates:
        2026-07-01 through 2026-07-07
    """
    if not isinstance(conf, Mapping) or not conf:
        raise ValueError("Backfill configuration must be a non-empty mapping.")

    try:
        pendulum.timezone(business_timezone)
    except Exception as exc:
        raise ValueError(
            f"Invalid business_timezone '{business_timezone}'."
        ) from exc

    backfill_type = _validate_backfill_type(conf.get("backfill_type"))

    start_local_raw = _parse_datetime(
        conf.get("start"),
        "start",
        business_timezone,
    )
    end_local_raw = _parse_datetime(
        conf.get("end"),
        "end",
        business_timezone,
    )

    # Hourly boundaries are normalized using floor/ceil.
    # This is more user-friendly than requiring exact hour-aligned input.
    start_local_hour = _floor_to_hour(start_local_raw)
    end_local_hour = _ceil_to_hour(end_local_raw)

    start_utc_hour = start_local_hour.in_timezone("UTC")
    end_utc_hour = end_local_hour.in_timezone("UTC")

    if backfill_type in {"hourly", "both"}:
        if start_utc_hour >= end_utc_hour:
            raise ValueError(
                f"Invalid hourly backfill interval: start '{start_local_raw}' "
                f"must be earlier than end '{end_local_raw}'."
            )

        if end_utc_hour > start_utc_hour.add(days=MAX_HOURLY_BACKFILL_DAYS):
            raise ValueError(
                f"Hourly backfill range must not exceed "
                f"{MAX_HOURLY_BACKFILL_DAYS} days."
            )

    # Daily date calculation.
    #
    # For daily-only, the input end date is inclusive.
    # For both, daily dates should be the affected dates from the hourly
    # half-open interval [start, end). Therefore if end is exactly midnight,
    # the end date itself is not affected.
    if backfill_type == "both":
        daily_start_date = start_local_hour.to_date_string()
        daily_end_date = end_local_hour.subtract(microseconds=1).to_date_string()
    else:
        daily_start_date = start_local_raw.to_date_string()
        daily_end_date = end_local_raw.to_date_string()

    if backfill_type in {"daily", "both"}:
        _validate_daily_range(
            daily_start_date,
            daily_end_date,
            max_days=MAX_DAILY_BACKFILL_DAYS,
        )

    return {
        "backfill_type": backfill_type,
        "business_timezone": business_timezone,
        "start_local": start_local_raw.to_iso8601_string(),
        "end_local": end_local_raw.to_iso8601_string(),
        "start_dt": start_utc_hour,
        "end_dt": end_utc_hour,
        "start": _to_db_timestamp(start_utc_hour),
        "end": _to_db_timestamp(end_utc_hour),
        "start_date": daily_start_date,
        "end_date": daily_end_date,
    }


def generate_hourly_windows(
    start_dt: pendulum.DateTime,
    end_dt: pendulum.DateTime,
) -> List[Tuple[str, str]]:
    """
    Generate hourly windows over [start_dt, end_dt).

    Returns:
        List of PostgreSQL-friendly timestamp string tuples.

    Example:
        [
            ("2026-07-01 00:00:00", "2026-07-01 01:00:00"),
            ("2026-07-01 01:00:00", "2026-07-01 02:00:00")
        ]
    """
    start_utc = _floor_to_hour(start_dt.in_timezone("UTC"))
    end_utc = _ceil_to_hour(end_dt.in_timezone("UTC"))

    if start_utc >= end_utc:
        raise ValueError("start_dt must be earlier than end_dt.")

    windows: List[Tuple[str, str]] = []

    current = start_utc
    while current < end_utc:
        next_hour = current.add(hours=1)
        windows.append(
            (
                _to_db_timestamp(current),
                _to_db_timestamp(next_hour),
            )
        )
        current = next_hour

    return windows


def generate_daily_dates(
    start_date: str,
    end_date: str,
) -> List[str]:
    """
    Generate daily dates over inclusive [start_date, end_date].

    Input:
        start_date: YYYY-MM-DD
        end_date: YYYY-MM-DD

    Returns:
        ["2026-07-01", "2026-07-02", ...]
    """
    _validate_daily_range(start_date, end_date)

    current = pendulum.parse(start_date)
    end = pendulum.parse(end_date)

    dates: List[str] = []

    while current <= end:
        dates.append(current.to_date_string())
        current = current.add(days=1)

    return dates


def cleanup_hourly_mart_window(
    target_hour_start: str,
    target_hour_end: str,
) -> Dict[str, int]:
    """
    Delete hourly mart data only within the target half-open window.

    Window:
        hour_bucket >= target_hour_start
        hour_bucket < target_hour_end

    Important:
        This function must never truncate or delete outside the target window.
    """
    target_hour_start = _require_non_empty_string(
        target_hour_start,
        "target_hour_start",
    )
    target_hour_end = _require_non_empty_string(
        target_hour_end,
        "target_hour_end",
    )

    params = {
        "target_hour_start": target_hour_start,
        "target_hour_end": target_hour_end,
    }

    where_sql = """
        WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
          AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
    """

    deleted_rows = {
        "weather_mobility_summary": int(
            execute_sql(
                f"DELETE FROM mart.weather_mobility_summary {where_sql}",
                params,
            )
            or 0
        ),
        "vehicle_type_availability_summary": int(
            execute_sql(
                f"DELETE FROM mart.vehicle_type_availability_summary {where_sql}",
                params,
            )
            or 0
        ),
        "hourly_region_availability": int(
            execute_sql(
                f"DELETE FROM mart.hourly_region_availability {where_sql}",
                params,
            )
            or 0
        ),
        "hourly_station_availability": int(
            execute_sql(
                f"DELETE FROM mart.hourly_station_availability {where_sql}",
                params,
            )
            or 0
        ),
    }

    logger.info(
        f"Cleaned hourly mart window "
        f"[{target_hour_start}, {target_hour_end}): {deleted_rows}"
    )

    return deleted_rows


def cleanup_daily_mart_date(target_date: str) -> Dict[str, int]:
    """
    Delete daily mart data only for the target_date.

    Important:
        This function must never truncate or delete outside target_date.
    """
    target_date = _require_non_empty_string(target_date, "target_date")

    try:
        normalized_date = date.fromisoformat(target_date).isoformat()
    except ValueError as exc:
        raise ValueError(
            f"Invalid target_date '{target_date}'. Expected YYYY-MM-DD."
        ) from exc

    params = {"target_date": normalized_date}

    deleted_rows = {
        "daily_system_summary": int(
            execute_sql(
                """
                DELETE FROM mart.daily_system_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                """,
                params,
            )
            or 0
        ),
        "station_demand_ranking": int(
            execute_sql(
                """
                DELETE FROM mart.station_demand_ranking
                WHERE ranking_date = CAST(:target_date AS DATE)
                """,
                params,
            )
            or 0
        ),
        "daily_region_summary": int(
            execute_sql(
                """
                DELETE FROM mart.daily_region_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                """,
                params,
            )
            or 0
        ),
        "daily_station_summary": int(
            execute_sql(
                """
                DELETE FROM mart.daily_station_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                """,
                params,
            )
            or 0
        ),
    }

    logger.info(
        f"Cleaned daily mart date {normalized_date}: {deleted_rows}"
    )

    return deleted_rows


def _require_row_count(
    value: Any,
    builder_name: str,
    *,
    allow_zero: bool = False,
) -> int:
    """
    Validate builder row count.

    Main mart builders should not silently return 0 rows.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(
            f"{builder_name} must return an integer row count. "
            f"Got {type(value).__name__}."
        )

    if value < 0:
        raise RuntimeError(
            f"{builder_name} returned invalid negative row count: {value}."
        )

    if value == 0 and not allow_zero:
        raise RuntimeError(
            f"{builder_name} built 0 rows for the target partition."
        )

    return value


def _validate_dq_result(result: Any, check_name: str) -> None:
    """
    Validate DQ check result.

    Supported contracts:
    1. Return None and raise exception on failure.
    2. Return bool.
    3. Return dict with passed=True/False or success=True/False.
    """
    if result is None:
        return

    if isinstance(result, bool):
        if not result:
            raise RuntimeError(f"{check_name} reported failure.")
        return

    if isinstance(result, Mapping):
        status = result.get("passed", result.get("success"))

        if status is False:
            details = result.get(
                "failed_checks",
                result.get("errors", result),
            )
            raise RuntimeError(
                f"{check_name} reported failure: {details}"
            )

        if status is True:
            return

    raise TypeError(
        f"{check_name} must return None, bool, or mapping containing "
        f"'passed'/'success'. Got {type(result).__name__}."
    )


def backfill_hourly_mart(
    target_hour_start: str,
    target_hour_end: str,
    batch_id: str,
    run_id: str,
    *,
    weather_enabled: bool = True,
    weather_required: bool = True,
    vehicle_type_required: bool = False,
) -> Dict[str, Any]:
    """
    Rebuild and validate one hourly mart window.

    This version is compatible with existing builder functions that do not
    accept a shared SQLAlchemy connection.

    Important:
    - Cleanup is limited to the exact target window.
    - Main tables must load > 0 rows.
    - Vehicle type summary can be optional by default.
    - Weather summary is built and required by default.
    """
    target_hour_start = _require_non_empty_string(
        target_hour_start,
        "target_hour_start",
    )
    target_hour_end = _require_non_empty_string(
        target_hour_end,
        "target_hour_end",
    )
    batch_id = _require_non_empty_string(batch_id, "batch_id")
    run_id = _require_non_empty_string(run_id, "run_id")

    start_dt = _parse_datetime(target_hour_start, "target_hour_start", "UTC")
    end_dt = _parse_datetime(target_hour_end, "target_hour_end", "UTC")

    start_utc = _floor_to_hour(start_dt.in_timezone("UTC"))
    end_utc = _floor_to_hour(end_dt.in_timezone("UTC"))

    if start_utc >= end_utc:
        raise ValueError(
            "target_hour_start must be earlier than target_hour_end."
        )

    if end_utc != start_utc.add(hours=1):
        raise ValueError(
            "backfill_hourly_mart requires exactly one one-hour window."
        )

    builder_start = _to_db_timestamp(start_utc)
    builder_end = _to_db_timestamp(end_utc)

    logger.info(
        f"Starting hourly mart backfill for window "
        f"[{builder_start}, {builder_end}), "
        f"batch_id={batch_id}, run_id={run_id}"
    )

    deleted_rows = cleanup_hourly_mart_window(
        target_hour_start=builder_start,
        target_hour_end=builder_end,
    )

    station_loaded = _require_row_count(
        build_hourly_station_availability(
            target_hour_start=builder_start,
            target_hour_end=builder_end,
            batch_id=batch_id,
            run_id=run_id,
        ),
        "build_hourly_station_availability",
    )

    region_loaded = _require_row_count(
        build_hourly_region_availability(
            target_hour_start=builder_start,
            target_hour_end=builder_end,
            batch_id=batch_id,
            run_id=run_id,
        ),
        "build_hourly_region_availability",
    )

    vehicle_type_loaded = _require_row_count(
        build_vehicle_type_availability_summary(
            target_hour_start=builder_start,
            target_hour_end=builder_end,
            batch_id=batch_id,
            run_id=run_id,
        ),
        "build_vehicle_type_availability_summary",
        allow_zero=not vehicle_type_required,
    )

    if vehicle_type_loaded == 0:
        logger.warning(
            f"Vehicle type mart produced 0 rows for "
            f"[{builder_start}, {builder_end}). Treated as optional."
        )

    weather_loaded = 0

    if weather_enabled:
        weather_loaded = _require_row_count(
            build_weather_mobility_summary(
                target_hour_start=builder_start,
                target_hour_end=builder_end,
                batch_id=batch_id,
                run_id=run_id,
            ),
            "build_weather_mobility_summary",
            allow_zero=not weather_required,
        )

        if weather_loaded == 0:
            logger.warning(
                f"Weather mobility mart produced 0 rows for "
                f"[{builder_start}, {builder_end}). Treated as optional."
            )
    else:
        logger.warning(
            f"Weather mart build is disabled for "
            f"[{builder_start}, {builder_end})."
        )

    dq_result = run_hourly_mart_dq_checks(
        run_id=run_id,
        batch_id=batch_id,
        target_hour_start=builder_start,
        target_hour_end=builder_end,
    )
    _validate_dq_result(dq_result, "run_hourly_mart_dq_checks")

    loaded_rows = {
        "hourly_station_availability": station_loaded,
        "hourly_region_availability": region_loaded,
        "vehicle_type_availability_summary": vehicle_type_loaded,
        "weather_mobility_summary": weather_loaded,
    }

    logger.info(
        f"Completed hourly mart backfill for "
        f"[{builder_start}, {builder_end}): {loaded_rows}"
    )

    return {
        "target_hour_start": builder_start,
        "target_hour_end": builder_end,
        "deleted_rows": deleted_rows,
        "loaded_rows": loaded_rows,
    }


def backfill_daily_mart(
    target_date: str,
    batch_id: str,
    run_id: str,
) -> Dict[str, Any]:
    """
    Rebuild and validate one daily mart date.

    Daily date is inclusive and represents exactly one business date.
    """
    target_date = _require_non_empty_string(target_date, "target_date")
    batch_id = _require_non_empty_string(batch_id, "batch_id")
    run_id = _require_non_empty_string(run_id, "run_id")

    try:
        normalized_date = date.fromisoformat(target_date).isoformat()
    except ValueError as exc:
        raise ValueError(
            f"Invalid target_date '{target_date}'. Expected YYYY-MM-DD."
        ) from exc

    logger.info(
        f"Starting daily mart backfill for target_date={normalized_date}, "
        f"batch_id={batch_id}, run_id={run_id}"
    )

    deleted_rows = cleanup_daily_mart_date(normalized_date)

    station_loaded = _require_row_count(
        build_daily_station_summary(
            target_date=normalized_date,
            batch_id=batch_id,
            run_id=run_id,
        ),
        "build_daily_station_summary",
    )

    region_loaded = _require_row_count(
        build_daily_region_summary(
            target_date=normalized_date,
            batch_id=batch_id,
            run_id=run_id,
        ),
        "build_daily_region_summary",
    )

    ranking_loaded = _require_row_count(
        build_station_demand_ranking(
            target_date=normalized_date,
            batch_id=batch_id,
            run_id=run_id,
        ),
        "build_station_demand_ranking",
    )

    system_loaded = _require_row_count(
        build_daily_system_summary(
            target_date=normalized_date,
            batch_id=batch_id,
            run_id=run_id,
        ),
        "build_daily_system_summary",
    )

    dq_result = run_daily_mart_dq_checks(
        run_id=run_id,
        batch_id=batch_id,
        target_date=normalized_date,
    )
    _validate_dq_result(dq_result, "run_daily_mart_dq_checks")

    loaded_rows = {
        "daily_station_summary": station_loaded,
        "daily_region_summary": region_loaded,
        "station_demand_ranking": ranking_loaded,
        "daily_system_summary": system_loaded,
    }

    logger.info(
        f"Completed daily mart backfill for "
        f"target_date={normalized_date}: {loaded_rows}"
    )

    return {
        "target_date": normalized_date,
        "deleted_rows": deleted_rows,
        "loaded_rows": loaded_rows,
    }


def _add_row_counts(
    target: Dict[str, int],
    source: Dict[str, int],
) -> None:
    """
    Add source row counts into target row count dictionary.
    """
    for table_name, row_count in source.items():
        target[table_name] = int(target.get(table_name, 0)) + int(row_count or 0)


def backfill_mart_range(
    backfill_type: str,
    start: str,
    end: str,
    batch_id: str,
    run_id: str,
    *,
    business_timezone: str = DEFAULT_BUSINESS_TIMEZONE,
    weather_enabled: bool = True,
    weather_required: bool = True,
    vehicle_type_required: bool = False,
    include_partition_details: bool = False,
) -> Dict[str, Any]:
    """
    Backfill mart tables for a selected range.

    Supported types:
    - hourly: rebuild hourly mart windows over [start, end)
    - daily: rebuild daily mart dates over [start_date, end_date] inclusive
    - both: rebuild hourly first, then affected daily dates

    If one window/date fails, this function raises the exception and fails
    the caller. It does not silently skip failed partitions.
    """
    batch_id = _require_non_empty_string(batch_id, "batch_id")
    run_id = _require_non_empty_string(run_id, "run_id")

    parsed = parse_backfill_conf(
        {
            "backfill_type": backfill_type,
            "start": start,
            "end": end,
        },
        business_timezone=business_timezone,
    )

    target_type = parsed["backfill_type"]

    hourly_rows_loaded_by_table = {
        "hourly_station_availability": 0,
        "hourly_region_availability": 0,
        "vehicle_type_availability_summary": 0,
        "weather_mobility_summary": 0,
    }

    daily_rows_loaded_by_table = {
        "daily_station_summary": 0,
        "daily_region_summary": 0,
        "station_demand_ranking": 0,
        "daily_system_summary": 0,
    }

    hourly_results: List[Dict[str, Any]] = []
    daily_results: List[Dict[str, Any]] = []

    hourly_windows_processed = 0
    daily_dates_processed = 0

    logger.info(
        f"Starting mart backfill range. "
        f"backfill_type={target_type}, "
        f"start={start}, end={end}, "
        f"business_timezone={business_timezone}, "
        f"batch_id={batch_id}, run_id={run_id}"
    )

    if target_type in {"hourly", "both"}:
        hourly_windows = generate_hourly_windows(
            parsed["start_dt"],
            parsed["end_dt"],
        )

        logger.info(
            f"Generated {len(hourly_windows)} hourly window(s) for backfill."
        )

        for target_hour_start, target_hour_end in hourly_windows:
            logger.info(
                f"Processing hourly backfill window "
                f"[{target_hour_start}, {target_hour_end})"
            )

            result = backfill_hourly_mart(
                target_hour_start=target_hour_start,
                target_hour_end=target_hour_end,
                batch_id=batch_id,
                run_id=run_id,
                weather_enabled=weather_enabled,
                weather_required=weather_required,
                vehicle_type_required=vehicle_type_required,
            )

            hourly_windows_processed += 1
            _add_row_counts(
                hourly_rows_loaded_by_table,
                result["loaded_rows"],
            )

            if include_partition_details:
                hourly_results.append(result)

    if target_type in {"daily", "both"}:
        daily_dates = generate_daily_dates(
            parsed["start_date"],
            parsed["end_date"],
        )

        logger.info(
            f"Generated {len(daily_dates)} daily date(s) for backfill."
        )

        for target_date in daily_dates:
            logger.info(
                f"Processing daily backfill date {target_date}"
            )

            result = backfill_daily_mart(
                target_date=target_date,
                batch_id=batch_id,
                run_id=run_id,
            )

            daily_dates_processed += 1
            _add_row_counts(
                daily_rows_loaded_by_table,
                result["loaded_rows"],
            )

            if include_partition_details:
                daily_results.append(result)

    total_records_loaded = (
        sum(hourly_rows_loaded_by_table.values())
        + sum(daily_rows_loaded_by_table.values())
    )

    summary: Dict[str, Any] = {
        "backfill_type": target_type,
        "business_timezone": business_timezone,
        "interval_start": parsed["start"],
        "interval_end": parsed["end"],
        "start_date": parsed["start_date"],
        "end_date": parsed["end_date"],
        "hourly_windows_processed": hourly_windows_processed,
        "daily_dates_processed": daily_dates_processed,
        "total_windows_or_dates_processed": (
            hourly_windows_processed + daily_dates_processed
        ),
        "total_records_loaded": total_records_loaded,
        "hourly_rows_loaded_by_table": hourly_rows_loaded_by_table,
        "daily_rows_loaded_by_table": daily_rows_loaded_by_table,
    }

    if include_partition_details:
        summary["hourly_results"] = hourly_results
        summary["daily_results"] = daily_results

    logger.info(
        f"Completed mart backfill range successfully. "
        f"backfill_type={target_type}, "
        f"hourly_windows_processed={hourly_windows_processed}, "
        f"daily_dates_processed={daily_dates_processed}, "
        f"total_records_loaded={total_records_loaded}"
    )

    return summary