from src.common.db import fetch_one
from src.common.logger import get_logger
from src.quality.metadata_checks import write_dq_result

logger = get_logger(__name__)


def run_weather_calendar_dq_checks(run_id: str, batch_id: str) -> None:
    """
    Run data quality checks for weather and calendar raw and staging layers.
    Raises ValueError if any CRITICAL check fails.
    """
    logger.info(
        f"Running weather and calendar data quality checks. "
        f"run_id={run_id} | batch_id={batch_id}"
    )

    checks = [
        # ==================================================
        # WEATHER RAW LAYER CHECKS
        # ==================================================
        {
            "table": "raw.weather_hourly",
            "name": "raw_weather_hourly_not_empty",
            "sql": """
                SELECT CASE WHEN COUNT(*) = 0 THEN 1 ELSE 0 END AS failed_count
                FROM raw.weather_hourly
                WHERE batch_id = :batch_id
            """,
            "severity": "CRITICAL",
            "msg_template": "Batch {batch_id}: raw.weather_hourly is empty.",
        },
        {
            "table": "raw.weather_hourly",
            "name": "raw_weather_hourly_time_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM raw.weather_hourly
                WHERE batch_id = :batch_id
                  AND weather_time IS NULL
            """,
            "severity": "CRITICAL",
            "msg_template": "Batch {batch_id}: Found {count} raw record(s) with NULL weather_time.",
        },
        {
            "table": "raw.weather_hourly",
            "name": "raw_weather_hourly_payload_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM raw.weather_hourly
                WHERE batch_id = :batch_id
                  AND raw_weather IS NULL
            """,
            "severity": "CRITICAL",
            "msg_template": "Batch {batch_id}: Found {count} raw record(s) with NULL raw_weather.",
        },
        {
            "table": "raw.weather_hourly",
            "name": "raw_weather_hourly_fetched_at_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM raw.weather_hourly
                WHERE batch_id = :batch_id
                  AND fetched_at IS NULL
            """,
            "severity": "CRITICAL",
            "msg_template": "Batch {batch_id}: Found {count} raw record(s) with NULL fetched_at.",
        },
        {
            "table": "raw.weather_hourly",
            "name": "raw_weather_hourly_location_name_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM raw.weather_hourly
                WHERE batch_id = :batch_id
                  AND (location_name IS NULL OR TRIM(location_name) = '')
            """,
            "severity": "CRITICAL",
            "msg_template": "Batch {batch_id}: Found {count} raw record(s) with NULL or empty location_name.",
        },
        {
            "table": "raw.weather_hourly",
            "name": "raw_weather_hourly_unique",
            "sql": """
                SELECT COALESCE(SUM(duplicate_count - 1), 0) AS failed_count
                FROM (
                    SELECT location_name, weather_time, batch_id, COUNT(*) AS duplicate_count
                    FROM raw.weather_hourly
                    WHERE batch_id = :batch_id
                    GROUP BY location_name, weather_time, batch_id
                    HAVING COUNT(*) > 1
                ) dup
            """,
            "severity": "CRITICAL",
            "msg_template": "Batch {batch_id}: Found {count} duplicate weather raw record(s) by location+time.",
        },
        # ==================================================
        # WEATHER STAGING LAYER CHECKS
        # ==================================================
        {
            "table": "staging.weather_hourly",
            "name": "staging_weather_hourly_not_empty",
            "sql": """
                SELECT CASE WHEN COUNT(*) = 0 THEN 1 ELSE 0 END AS failed_count
                FROM staging.weather_hourly
                WHERE batch_id = :batch_id
            """,
            "severity": "CRITICAL",
            "msg_template": "Batch {batch_id}: staging.weather_hourly is empty.",
        },
        {
            "table": "staging.weather_hourly",
            "name": "staging_weather_hourly_time_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.weather_hourly
                WHERE batch_id = :batch_id
                  AND weather_time IS NULL
            """,
            "severity": "CRITICAL",
            "msg_template": "Batch {batch_id}: Found {count} staging record(s) with NULL weather_time.",
        },
        {
            "table": "staging.weather_hourly",
            "name": "staging_weather_hourly_temp_in_range",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.weather_hourly
                WHERE batch_id = :batch_id
                  AND temperature IS NOT NULL
                  AND (temperature < -50 OR temperature > 60)
            """,
            "severity": "CRITICAL",
            "msg_template": "Batch {batch_id}: Found {count} staging record(s) with temperature outside [-50, 60] range.",
        },
        {
            "table": "staging.weather_hourly",
            "name": "staging_weather_hourly_precipitation_non_negative",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.weather_hourly
                WHERE batch_id = :batch_id
                  AND precipitation IS NOT NULL
                  AND precipitation < 0
            """,
            "severity": "CRITICAL",
            "msg_template": "Batch {batch_id}: Found {count} staging record(s) with negative precipitation.",
        },
        {
            "table": "staging.weather_hourly",
            "name": "staging_weather_hourly_wind_speed_non_negative",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.weather_hourly
                WHERE batch_id = :batch_id
                  AND wind_speed IS NOT NULL
                  AND wind_speed < 0
            """,
            "severity": "CRITICAL",
            "msg_template": "Batch {batch_id}: Found {count} staging record(s) with negative wind_speed.",
        },
        {
            "table": "staging.weather_hourly",
            "name": "staging_weather_hourly_fetched_at_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.weather_hourly
                WHERE batch_id = :batch_id
                  AND fetched_at IS NULL
            """,
            "severity": "CRITICAL",
            "msg_template": "Batch {batch_id}: Found {count} staging record(s) with NULL fetched_at.",
        },
        {
            "table": "staging.weather_hourly",
            "name": "weather_raw_to_staging_count_match",
            "sql": """
                WITH raw_cnt AS (
                    SELECT COUNT(*) AS cnt FROM raw.weather_hourly WHERE batch_id = :batch_id
                ),
                stg_cnt AS (
                    SELECT COUNT(*) AS cnt FROM staging.weather_hourly WHERE batch_id = :batch_id
                )
                SELECT ABS(raw_cnt.cnt - stg_cnt.cnt) AS failed_count
                FROM raw_cnt, stg_cnt
            """,
            "severity": "CRITICAL",
            "msg_template": "Batch {batch_id}: Weather raw ({count} difference) staging counts mismatch.",
        },
        # ==================================================
        # CALENDAR RAW LAYER CHECKS
        # ==================================================
        {
            "table": "raw.calendar",
            "name": "raw_calendar_not_empty",
            "sql": """
                SELECT CASE WHEN COUNT(*) = 0 THEN 1 ELSE 0 END AS failed_count
                FROM raw.calendar
                WHERE batch_id = :batch_id
            """,
            "severity": "CRITICAL",
            "msg_template": "Batch {batch_id}: raw.calendar is empty.",
        },
        {
            "table": "raw.calendar",
            "name": "raw_calendar_date_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM raw.calendar
                WHERE batch_id = :batch_id
                  AND calendar_date IS NULL
            """,
            "severity": "CRITICAL",
            "msg_template": "Batch {batch_id}: Found {count} raw calendar record(s) with NULL calendar_date.",
        },
        {
            "table": "raw.calendar",
            "name": "raw_calendar_payload_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM raw.calendar
                WHERE batch_id = :batch_id
                  AND raw_calendar IS NULL
            """,
            "severity": "CRITICAL",
            "msg_template": "Batch {batch_id}: Found {count} raw calendar record(s) with NULL raw_calendar.",
        },
        {
            "table": "raw.calendar",
            "name": "raw_calendar_unique",
            "sql": """
                SELECT COALESCE(SUM(duplicate_count - 1), 0) AS failed_count
                FROM (
                    SELECT calendar_date, batch_id, COUNT(*) AS duplicate_count
                    FROM raw.calendar
                    WHERE batch_id = :batch_id
                    GROUP BY calendar_date, batch_id
                    HAVING COUNT(*) > 1
                ) dup
            """,
            "severity": "CRITICAL",
            "msg_template": "Batch {batch_id}: Found {count} duplicate calendar dates in raw layer.",
        },
        # ==================================================
        # CALENDAR STAGING LAYER CHECKS
        # ==================================================
        {
            "table": "staging.calendar",
            "name": "staging_calendar_not_empty",
            "sql": """
                SELECT CASE WHEN COUNT(*) = 0 THEN 1 ELSE 0 END AS failed_count
                FROM staging.calendar
                WHERE batch_id = :batch_id
            """,
            "severity": "CRITICAL",
            "msg_template": "Batch {batch_id}: staging.calendar is empty.",
        },
        {
            "table": "staging.calendar",
            "name": "staging_calendar_date_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.calendar
                WHERE batch_id = :batch_id
                  AND calendar_date IS NULL
            """,
            "severity": "CRITICAL",
            "msg_template": "Batch {batch_id}: Found {count} staging record(s) with NULL calendar_date.",
        },
        {
            "table": "staging.calendar",
            "name": "staging_calendar_day_of_week_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.calendar
                WHERE batch_id = :batch_id
                  AND day_of_week IS NULL
            """,
            "severity": "CRITICAL",
            "msg_template": "Batch {batch_id}: Found {count} staging record(s) with NULL day_of_week.",
        },
        {
            "table": "staging.calendar",
            "name": "staging_calendar_is_weekend_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.calendar
                WHERE batch_id = :batch_id
                  AND is_weekend IS NULL
            """,
            "severity": "CRITICAL",
            "msg_template": "Batch {batch_id}: Found {count} staging record(s) with NULL is_weekend.",
        },
        {
            "table": "staging.calendar",
            "name": "staging_calendar_is_holiday_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.calendar
                WHERE batch_id = :batch_id
                  AND is_holiday IS NULL
            """,
            "severity": "CRITICAL",
            "msg_template": "Batch {batch_id}: Found {count} staging record(s) with NULL is_holiday.",
        },
        {
            "table": "staging.calendar",
            "name": "calendar_raw_to_staging_count_match",
            "sql": """
                WITH raw_cnt AS (
                    SELECT COUNT(*) AS cnt FROM raw.calendar WHERE batch_id = :batch_id
                ),
                stg_cnt AS (
                    SELECT COUNT(*) AS cnt FROM staging.calendar WHERE batch_id = :batch_id
                )
                SELECT ABS(raw_cnt.cnt - stg_cnt.cnt) AS failed_count
                FROM raw_cnt, stg_cnt
            """,
            "severity": "CRITICAL",
            "msg_template": "Batch {batch_id}: Calendar raw ({count} difference) staging counts mismatch.",
        },
    ]

    critical_failures = []

    for check in checks:
        try:
            result = fetch_one(check["sql"], {"batch_id": batch_id})
            failed_count = int(result["failed_count"] or 0) if result else 0

            if failed_count > 0:
                message = check["msg_template"].format(
                    batch_id=batch_id,
                    count=failed_count,
                )
                status = "failed"

                if check["severity"] == "CRITICAL":
                    logger.error(
                        f"DQ Check FAILED: {check['name']} "
                        f"on {check['table']} - {message}"
                    )
                    critical_failures.append(f"{check['name']}: {message}")
                else:
                    logger.warning(
                        f"DQ Check WARNING: {check['name']} "
                        f"on {check['table']} - {message}"
                    )
            else:
                status = "passed"
                message = f"Batch {batch_id}: All records passed check."
                logger.info(
                    f"DQ Check PASSED: {check['name']} on {check['table']}"
                )

            write_dq_result(
                run_id=run_id,
                table_name=check["table"],
                check_name=check["name"],
                status=status,
                failed_count=failed_count,
                severity=check["severity"],
                message=message,
            )

        except Exception as e:
            error_message = (
                f"Batch {batch_id}: Execution error while running "
                f"DQ check '{check['name']}': {e}"
            )
            logger.error(error_message)

            write_dq_result(
                run_id=run_id,
                table_name=check["table"],
                check_name=check["name"],
                status="failed",
                failed_count=1,
                severity=check["severity"],
                message=error_message,
            )
            if check["severity"] == "CRITICAL":
                critical_failures.append(
                    f"{check['name']} execution error: {e}"
                )

    if critical_failures:
        error_message = "; ".join(critical_failures)
        logger.error(
            f"Critical weather_calendar data quality check failures: "
            f"{error_message}"
        )
        raise ValueError(
            f"Critical weather_calendar DQ checks failed: {error_message}"
        )

    logger.info(
        f"All weather_calendar data quality checks executed successfully "
        f"for batch_id={batch_id}."
    )
