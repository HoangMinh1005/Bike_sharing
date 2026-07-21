import json
from datetime import datetime
from typing import Any, Dict, Optional

from src.common.db import execute_sql, fetch_all
from src.common.logger import get_logger

logger = get_logger(__name__)


def _parse_bool(val: Any) -> bool:
    if val is None:
        return False
    if isinstance(val, bool):
        return val
    if isinstance(val, int):
        return val != 0
    if isinstance(val, str):
        return val.strip().lower() in ("true", "1", "yes")
    return False


def _parse_raw_calendar(raw_val: Any) -> Optional[Dict[str, Any]]:
    if isinstance(raw_val, dict):
        return raw_val
    if isinstance(raw_val, str):
        try:
            return json.loads(raw_val)
        except Exception as e:
            logger.warning(f"Failed to parse raw_calendar JSON string: {e}")
            return None
    return None


def transform_calendar(batch_id: str) -> int:
    """
    Transform raw.calendar snapshots into staging.calendar.
    Uses calendar_date + batch_id as conflict target.

    Returns the number of processed calendar days.
    """
    logger.info(f"Transforming calendar records for batch={batch_id}")

    sql_select = """
        SELECT
            calendar_date,
            raw_calendar
        FROM raw.calendar
        WHERE batch_id = :batch_id
    """

    rows = fetch_all(sql_select, {"batch_id": batch_id})
    if not rows:
        logger.warning(f"No raw calendar records found for batch_id={batch_id}")
        return 0

    sql_upsert = """
        INSERT INTO staging.calendar (
            calendar_date,
            day_of_week,
            is_weekend,
            is_holiday,
            holiday_name,
            batch_id,
            updated_at
        ) VALUES (
            :calendar_date,
            :day_of_week,
            :is_weekend,
            :is_holiday,
            :holiday_name,
            :batch_id,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (calendar_date, batch_id) DO UPDATE SET
            day_of_week = EXCLUDED.day_of_week,
            is_weekend = EXCLUDED.is_weekend,
            is_holiday = EXCLUDED.is_holiday,
            holiday_name = EXCLUDED.holiday_name,
            updated_at = CURRENT_TIMESTAMP
    """

    processed = 0

    for row in rows:
        calendar_date = row["calendar_date"]
        raw_calendar_val = row["raw_calendar"]

        raw_calendar = _parse_raw_calendar(raw_calendar_val)
        if raw_calendar is None:
            logger.warning(f"Skipping calendar record for date={calendar_date} due to missing payload.")
            continue

        # Extract values with fallbacks
        day_of_week = raw_calendar.get("day_of_week")
        if not day_of_week:
            day_of_week = calendar_date.strftime("%A")

        is_weekend_val = raw_calendar.get("is_weekend")
        if is_weekend_val is None:
            is_weekend = calendar_date.weekday() >= 5
        else:
            is_weekend = _parse_bool(is_weekend_val)

        is_holiday = _parse_bool(raw_calendar.get("is_holiday"))
        holiday_name = raw_calendar.get("holiday_name") or None

        params = {
            "calendar_date": calendar_date,
            "day_of_week": day_of_week,
            "is_weekend": is_weekend,
            "is_holiday": is_holiday,
            "holiday_name": holiday_name,
            "batch_id": batch_id,
        }

        try:
            execute_sql(sql_upsert, params)
            processed += 1
        except Exception as e:
            logger.error(
                f"Failed to transform calendar record for date={calendar_date}: {e}"
            )
            raise

    logger.info(
        f"Transformed calendar to staging: processed={processed} record(s)"
    )

    return processed
