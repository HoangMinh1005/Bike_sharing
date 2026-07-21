import csv
import hashlib
import json
import os
from datetime import datetime
from typing import Any, Dict

from src.common.db import execute_sql
from src.common.logger import get_logger

logger = get_logger(__name__)


def compute_calendar_hash(record: Dict[str, Any]) -> str:
    """
    Compute SHA256 hash of an individual calendar CSV row.
    """
    serialized = json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def load_calendar_raw(
    csv_path: str,
    batch_id: str,
    run_id: str
) -> int:
    """
    Read the local calendar CSV and load records into raw.calendar.

    Returns the number of records successfully loaded.
    Raises FileNotFoundError if the CSV does not exist.
    Raises ValueError if columns are invalid.
    """
    logger.info(
        f"Loading raw calendar records from CSV: {csv_path} | "
        f"batch_id={batch_id}, run_id={run_id}"
    )

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Calendar CSV file not found at: {csv_path}")

    # Read CSV rows
    rows = []
    try:
        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = [h.strip().lower() for h in reader.fieldnames or []]
            
            if "date" not in headers:
                raise ValueError(
                    f"Invalid calendar CSV header format. Missing required 'date' column. "
                    f"Headers found: {reader.fieldnames}"
                )

            for row in reader:
                # Standardize keys to lowercase
                cleaned_row = {k.strip().lower(): v.strip() for k, v in row.items() if k is not None}
                rows.append(cleaned_row)
    except Exception as e:
        logger.error(f"Failed to read calendar CSV file: {e}")
        raise

    insert_sql = """
        INSERT INTO raw.calendar (
            batch_id,
            run_id,
            calendar_date,
            raw_calendar,
            payload_hash,
            loaded_at
        ) VALUES (
            :batch_id,
            :run_id,
            :calendar_date,
            CAST(:raw_calendar AS JSONB),
            :payload_hash,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (batch_id, calendar_date) DO UPDATE SET
            raw_calendar = EXCLUDED.raw_calendar,
            payload_hash = EXCLUDED.payload_hash,
            run_id = EXCLUDED.run_id,
            loaded_at = CURRENT_TIMESTAMP
    """

    loaded_count = 0

    for idx, row in enumerate(rows):
        date_str = row.get("date")
        if not date_str:
            logger.warning(f"Row {idx + 1} is missing date string, skipping.")
            continue

        try:
            # Parse to datetime.date object
            calendar_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError as e:
            logger.warning(
                f"Row {idx + 1} has invalid date string '{date_str}', skipping. Error: {e}"
            )
            continue

        # Re-construct raw payload mapping
        raw_calendar_dict = {
            "date": date_str,
            "day_of_week": row.get("day_of_week", ""),
            "is_weekend": row.get("is_weekend", "false"),
            "is_holiday": row.get("is_holiday", "false"),
            "holiday_name": row.get("holiday_name", "")
        }

        payload_hash = compute_calendar_hash(raw_calendar_dict)
        raw_calendar_json = json.dumps(raw_calendar_dict, ensure_ascii=False)

        params = {
            "batch_id": batch_id,
            "run_id": run_id,
            "calendar_date": calendar_date,
            "raw_calendar": raw_calendar_json,
            "payload_hash": payload_hash
        }

        try:
            execute_sql(insert_sql, params)
            loaded_count += 1
        except Exception as e:
            logger.error(
                f"Failed to load calendar record for date={date_str}: {e}"
            )
            raise

    logger.info(
        f"Raw calendar loading completed. "
        f"loaded_or_upserted={loaded_count} record(s)"
    )

    return loaded_count
