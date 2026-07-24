from src.common.db import fetch_one
from src.common.logger import get_logger
from src.quality.metadata_checks import write_dq_result

logger = get_logger(__name__)


def run_hourly_mart_dq_checks(
    run_id: str,
    batch_id: str,
    target_hour_start: str,
    target_hour_end: str,
) -> None:
    """
    Run data quality checks for hourly mart tables in the target window.

    Tables checked:
    - mart.hourly_station_availability
    - mart.hourly_region_availability
    - mart.vehicle_type_availability_summary
    - mart.weather_mobility_summary

    Critical checks raise ValueError and fail the pipeline.
    Warning checks are written to etl_metadata.dq_results but do not fail the pipeline.

    Note:
        DQ checks use target hour window instead of batch_id because hourly mart
        tables are keyed by business grain, for example:
        - hour_bucket + station_id
        - hour_bucket + region_id
        - hour_bucket + vehicle_type_id
        - hour_bucket
    """
    logger.info(
        f"Running hourly mart data quality checks. "
        f"run_id={run_id}, batch_id={batch_id}, "
        f"window=[{target_hour_start} to {target_hour_end}]"
    )

    params = {
        "target_hour_start": target_hour_start,
        "target_hour_end": target_hour_end,
    }

    checks = [
        # ==================================================
        # 1. mart.hourly_station_availability CHECKS
        # ==================================================
        {
            "table": "mart.hourly_station_availability",
            "name": "hourly_station_availability_not_empty",
            "sql": """
                SELECT CASE WHEN COUNT(*) = 0 THEN 1 ELSE 0 END AS failed_count
                FROM mart.hourly_station_availability
                WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
                  AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Window [{target_hour_start} to {target_hour_end}]: "
                "mart.hourly_station_availability is empty."
            ),
        },
        {
            "table": "mart.hourly_station_availability",
            "name": "hourly_station_availability_station_id_not_null_or_empty",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.hourly_station_availability
                WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
                  AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
                  AND (
                      station_id IS NULL
                      OR TRIM(CAST(station_id AS TEXT)) = ''
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Window [{target_hour_start} to {target_hour_end}]: Found {count} "
                "station availability record(s) with NULL or empty station_id."
            ),
        },
        {
            "table": "mart.hourly_station_availability",
            "name": "hourly_station_availability_observation_count_positive",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.hourly_station_availability
                WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
                  AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
                  AND (
                      observation_count IS NULL
                      OR observation_count <= 0
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Window [{target_hour_start} to {target_hour_end}]: Found {count} "
                "station availability record(s) with observation_count <= 0 or NULL."
            ),
        },
        {
            "table": "mart.hourly_station_availability",
            "name": "hourly_station_availability_core_metrics_valid",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.hourly_station_availability
                WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
                  AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
                  AND (
                      avg_bikes_available IS NULL
                      OR avg_bikes_available < 0
                      OR avg_docks_available IS NULL
                      OR avg_docks_available < 0
                      OR avg_bikes_disabled IS NULL
                      OR avg_bikes_disabled < 0
                      OR avg_docks_disabled IS NULL
                      OR avg_docks_disabled < 0
                      OR min_bikes_available IS NULL
                      OR min_bikes_available < 0
                      OR max_bikes_available IS NULL
                      OR max_bikes_available < 0
                      OR min_bikes_available > max_bikes_available
                      OR empty_observation_count IS NULL
                      OR empty_observation_count < 0
                      OR full_observation_count IS NULL
                      OR full_observation_count < 0
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Window [{target_hour_start} to {target_hour_end}]: Found {count} "
                "station availability record(s) with invalid core metrics."
            ),
        },
        {
            "table": "mart.hourly_station_availability",
            "name": "hourly_station_availability_valid_availability_rate",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.hourly_station_availability
                WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
                  AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
                  AND availability_rate IS NOT NULL
                  AND (
                      availability_rate < 0
                      OR availability_rate > 1
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Window [{target_hour_start} to {target_hour_end}]: Found {count} "
                "station availability record(s) with availability_rate outside [0, 1]."
            ),
        },
        {
            "table": "mart.hourly_station_availability",
            "name": "hourly_station_availability_valid_dock_utilization_rate",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.hourly_station_availability
                WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
                  AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
                  AND dock_utilization_rate IS NOT NULL
                  AND (
                      dock_utilization_rate < 0
                      OR dock_utilization_rate > 1
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Window [{target_hour_start} to {target_hour_end}]: Found {count} "
                "station availability record(s) with dock_utilization_rate outside [0, 1]."
            ),
        },
        {
            "table": "mart.hourly_station_availability",
            "name": "hourly_station_availability_unique_station_hour",
            "sql": """
                SELECT COALESCE(SUM(duplicate_count - 1), 0) AS failed_count
                FROM (
                    SELECT
                        hour_bucket,
                        station_id,
                        COUNT(*) AS duplicate_count
                    FROM mart.hourly_station_availability
                    WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
                      AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
                    GROUP BY
                        hour_bucket,
                        station_id
                    HAVING COUNT(*) > 1
                ) dup
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Window [{target_hour_start} to {target_hour_end}]: Found {count} "
                "duplicate station mart record(s) by hour_bucket + station_id."
            ),
        },
        {
            "table": "mart.hourly_station_availability",
            "name": "hourly_station_availability_missing_station_metadata",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.hourly_station_availability
                WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
                  AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
                  AND station_name IS NULL
            """,
            "severity": "WARNING",
            "msg_template": (
                "Window [{target_hour_start} to {target_hour_end}]: Found {count} "
                "station availability record(s) missing station metadata."
            ),
        },
        {
            "table": "mart.hourly_station_availability",
            "name": "hourly_station_availability_missing_region_metadata",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.hourly_station_availability
                WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
                  AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
                  AND region_name IS NULL
            """,
            "severity": "WARNING",
            "msg_template": (
                "Window [{target_hour_start} to {target_hour_end}]: Found {count} "
                "station availability record(s) missing region metadata."
            ),
        },
        {
            "table": "mart.hourly_station_availability",
            "name": "hourly_station_availability_missing_weather",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.hourly_station_availability
                WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
                  AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
                  AND temperature IS NULL
            """,
            "severity": "WARNING",
            "msg_template": (
                "Window [{target_hour_start} to {target_hour_end}]: Found {count} "
                "station availability record(s) missing weather enrichment."
            ),
        },
        {
            "table": "mart.hourly_station_availability",
            "name": "hourly_station_availability_missing_calendar",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.hourly_station_availability
                WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
                  AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
                  AND calendar_date IS NULL
            """,
            "severity": "WARNING",
            "msg_template": (
                "Window [{target_hour_start} to {target_hour_end}]: Found {count} "
                "station availability record(s) missing calendar enrichment."
            ),
        },

        # ==================================================
        # 2. mart.hourly_region_availability CHECKS
        # ==================================================
        {
            "table": "mart.hourly_region_availability",
            "name": "hourly_region_availability_not_empty",
            "sql": """
                SELECT CASE WHEN COUNT(*) = 0 THEN 1 ELSE 0 END AS failed_count
                FROM mart.hourly_region_availability
                WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
                  AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Window [{target_hour_start} to {target_hour_end}]: "
                "mart.hourly_region_availability is empty."
            ),
        },
        {
            "table": "mart.hourly_region_availability",
            "name": "hourly_region_availability_unique_region_hour",
            "sql": """
                SELECT COALESCE(SUM(duplicate_count - 1), 0) AS failed_count
                FROM (
                    SELECT
                        hour_bucket,
                        region_id,
                        COUNT(*) AS duplicate_count
                    FROM mart.hourly_region_availability
                    WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
                      AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
                    GROUP BY
                        hour_bucket,
                        region_id
                    HAVING COUNT(*) > 1
                ) dup
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Window [{target_hour_start} to {target_hour_end}]: Found {count} "
                "duplicate region mart record(s) by hour_bucket + region_id."
            ),
        },
        {
            "table": "mart.hourly_region_availability",
            "name": "hourly_region_availability_station_count_valid",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.hourly_region_availability
                WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
                  AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
                  AND (
                      station_count IS NULL
                      OR station_count <= 0
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Window [{target_hour_start} to {target_hour_end}]: Found {count} "
                "region mart record(s) with invalid station_count."
            ),
        },
        {
            "table": "mart.hourly_region_availability",
            "name": "hourly_region_availability_active_station_count_valid",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.hourly_region_availability
                WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
                  AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
                  AND (
                      active_station_count IS NULL
                      OR active_station_count < 0
                      OR station_count IS NULL
                      OR active_station_count > station_count
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Window [{target_hour_start} to {target_hour_end}]: Found {count} "
                "region mart record(s) with invalid active_station_count."
            ),
        },
        {
            "table": "mart.hourly_region_availability",
            "name": "hourly_region_availability_core_metrics_valid",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.hourly_region_availability
                WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
                  AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
                  AND (
                      total_observation_count IS NULL
                      OR total_observation_count <= 0
                      OR avg_bikes_available IS NULL
                      OR avg_bikes_available < 0
                      OR avg_docks_available IS NULL
                      OR avg_docks_available < 0
                      OR total_bikes_available IS NULL
                      OR total_bikes_available < 0
                      OR total_docks_available IS NULL
                      OR total_docks_available < 0
                      OR empty_station_count IS NULL
                      OR empty_station_count < 0
                      OR full_station_count IS NULL
                      OR full_station_count < 0
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Window [{target_hour_start} to {target_hour_end}]: Found {count} "
                "region mart record(s) with invalid core metrics."
            ),
        },
        {
            "table": "mart.hourly_region_availability",
            "name": "hourly_region_availability_valid_availability_rate",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.hourly_region_availability
                WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
                  AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
                  AND avg_availability_rate IS NOT NULL
                  AND (
                      avg_availability_rate < 0
                      OR avg_availability_rate > 1
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Window [{target_hour_start} to {target_hour_end}]: Found {count} "
                "region mart record(s) with avg_availability_rate outside [0, 1]."
            ),
        },
        {
            "table": "mart.hourly_region_availability",
            "name": "hourly_region_availability_valid_dock_utilization_rate",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.hourly_region_availability
                WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
                  AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
                  AND avg_dock_utilization_rate IS NOT NULL
                  AND (
                      avg_dock_utilization_rate < 0
                      OR avg_dock_utilization_rate > 1
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Window [{target_hour_start} to {target_hour_end}]: Found {count} "
                "region mart record(s) with avg_dock_utilization_rate outside [0, 1]."
            ),
        },
        {
            "table": "mart.hourly_region_availability",
            "name": "hourly_region_availability_missing_region_name",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.hourly_region_availability
                WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
                  AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
                  AND region_name IS NULL
            """,
            "severity": "WARNING",
            "msg_template": (
                "Window [{target_hour_start} to {target_hour_end}]: Found {count} "
                "region mart record(s) missing region_name."
            ),
        },

        # ==================================================
        # 3. mart.vehicle_type_availability_summary CHECKS
        # ==================================================
        {
            "table": "mart.vehicle_type_availability_summary",
            "name": "vehicle_type_summary_not_empty",
            "sql": """
                SELECT CASE WHEN COUNT(*) = 0 THEN 1 ELSE 0 END AS failed_count
                FROM mart.vehicle_type_availability_summary
                WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
                  AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
            """,
            "severity": "WARNING",
            "msg_template": (
                "Window [{target_hour_start} to {target_hour_end}]: "
                "mart.vehicle_type_availability_summary is empty."
            ),
        },
        {
            "table": "mart.vehicle_type_availability_summary",
            "name": "vehicle_type_summary_vehicle_type_id_not_null_or_empty",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.vehicle_type_availability_summary
                WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
                  AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
                  AND (
                      vehicle_type_id IS NULL
                      OR TRIM(CAST(vehicle_type_id AS TEXT)) = ''
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Window [{target_hour_start} to {target_hour_end}]: Found {count} "
                "vehicle type summary record(s) with NULL or empty vehicle_type_id."
            ),
        },
        {
            "table": "mart.vehicle_type_availability_summary",
            "name": "vehicle_type_summary_unique_vehicle_type_hour",
            "sql": """
                SELECT COALESCE(SUM(duplicate_count - 1), 0) AS failed_count
                FROM (
                    SELECT
                        hour_bucket,
                        vehicle_type_id,
                        COUNT(*) AS duplicate_count
                    FROM mart.vehicle_type_availability_summary
                    WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
                      AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
                    GROUP BY
                        hour_bucket,
                        vehicle_type_id
                    HAVING COUNT(*) > 1
                ) dup
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Window [{target_hour_start} to {target_hour_end}]: Found {count} "
                "duplicate vehicle type summary record(s) by hour_bucket + vehicle_type_id."
            ),
        },
        {
            "table": "mart.vehicle_type_availability_summary",
            "name": "vehicle_type_summary_metrics_valid",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.vehicle_type_availability_summary
                WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
                  AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
                  AND (
                      station_count IS NULL
                      OR station_count <= 0
                      OR total_vehicle_count IS NULL
                      OR total_vehicle_count < 0
                      OR avg_vehicle_count_per_station IS NULL
                      OR avg_vehicle_count_per_station < 0
                      OR min_vehicle_count IS NULL
                      OR min_vehicle_count < 0
                      OR max_vehicle_count IS NULL
                      OR max_vehicle_count < 0
                      OR min_vehicle_count > max_vehicle_count
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Window [{target_hour_start} to {target_hour_end}]: Found {count} "
                "vehicle type summary record(s) with invalid metrics."
            ),
        },

        # ==================================================
        # 4. mart.weather_mobility_summary CHECKS
        # ==================================================
        {
            "table": "mart.weather_mobility_summary",
            "name": "weather_mobility_summary_not_empty",
            "sql": """
                SELECT CASE WHEN COUNT(*) = 0 THEN 1 ELSE 0 END AS failed_count
                FROM mart.weather_mobility_summary
                WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
                  AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Window [{target_hour_start} to {target_hour_end}]: "
                "mart.weather_mobility_summary is empty."
            ),
        },
        {
            "table": "mart.weather_mobility_summary",
            "name": "weather_mobility_summary_unique_hour",
            "sql": """
                SELECT COALESCE(SUM(duplicate_count - 1), 0) AS failed_count
                FROM (
                    SELECT
                        hour_bucket,
                        COUNT(*) AS duplicate_count
                    FROM mart.weather_mobility_summary
                    WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
                      AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
                    GROUP BY
                        hour_bucket
                    HAVING COUNT(*) > 1
                ) dup
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Window [{target_hour_start} to {target_hour_end}]: Found {count} "
                "duplicate weather mobility summary record(s) by hour_bucket."
            ),
        },
        {
            "table": "mart.weather_mobility_summary",
            "name": "weather_mobility_summary_core_metrics_valid",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.weather_mobility_summary
                WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
                  AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
                  AND (
                      station_count IS NULL
                      OR station_count <= 0
                      OR active_station_count IS NULL
                      OR active_station_count < 0
                      OR active_station_count > station_count
                      OR total_bikes_available IS NULL
                      OR total_bikes_available < 0
                      OR total_docks_available IS NULL
                      OR total_docks_available < 0
                      OR empty_station_count IS NULL
                      OR empty_station_count < 0
                      OR full_station_count IS NULL
                      OR full_station_count < 0
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Window [{target_hour_start} to {target_hour_end}]: Found {count} "
                "weather mobility summary record(s) with invalid core metrics."
            ),
        },
        {
            "table": "mart.weather_mobility_summary",
            "name": "weather_mobility_summary_valid_availability_rate",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.weather_mobility_summary
                WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
                  AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
                  AND avg_availability_rate IS NOT NULL
                  AND (
                      avg_availability_rate < 0
                      OR avg_availability_rate > 1
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Window [{target_hour_start} to {target_hour_end}]: Found {count} "
                "weather mobility summary record(s) with avg_availability_rate outside [0, 1]."
            ),
        },
        {
            "table": "mart.weather_mobility_summary",
            "name": "weather_mobility_summary_valid_dock_utilization_rate",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.weather_mobility_summary
                WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
                  AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
                  AND avg_dock_utilization_rate IS NOT NULL
                  AND (
                      avg_dock_utilization_rate < 0
                      OR avg_dock_utilization_rate > 1
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Window [{target_hour_start} to {target_hour_end}]: Found {count} "
                "weather mobility summary record(s) with avg_dock_utilization_rate outside [0, 1]."
            ),
        },
        {
            "table": "mart.weather_mobility_summary",
            "name": "weather_mobility_summary_missing_weather",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.weather_mobility_summary
                WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
                  AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
                  AND temperature IS NULL
            """,
            "severity": "WARNING",
            "msg_template": (
                "Window [{target_hour_start} to {target_hour_end}]: Found {count} "
                "weather mobility summary record(s) missing weather enrichment."
            ),
        },
        {
            "table": "mart.weather_mobility_summary",
            "name": "weather_mobility_summary_missing_calendar",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.weather_mobility_summary
                WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
                  AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
                  AND calendar_date IS NULL
            """,
            "severity": "WARNING",
            "msg_template": (
                "Window [{target_hour_start} to {target_hour_end}]: Found {count} "
                "weather mobility summary record(s) missing calendar enrichment."
            ),
        },
    ]

    critical_failures = []

    for check in checks:
        try:
            result = fetch_one(check["sql"], params)
            failed_count = int(result["failed_count"] or 0) if result else 0

            if failed_count > 0:
                message = check["msg_template"].format(
                    target_hour_start=target_hour_start,
                    target_hour_end=target_hour_end,
                    count=failed_count,
                )

                status = "failed"

                if check["severity"] == "CRITICAL":
                    logger.error(
                        f"DQ Check FAILED: {check['name']} "
                        f"on {check['table']} - {message}"
                    )

                    critical_failures.append(
                        f"{check['name']}: {message}"
                    )

                else:
                    logger.warning(
                        f"DQ Check WARNING: {check['name']} "
                        f"on {check['table']} - {message}"
                    )

            else:
                status = "passed"
                message = (
                    f"Window [{target_hour_start} to {target_hour_end}]: "
                    f"All records passed check."
                )

                logger.info(
                    f"DQ Check PASSED: {check['name']} "
                    f"on {check['table']}"
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
                f"Execution error while running DQ check "
                f"'{check['name']}' on {check['table']}: {e}"
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
            f"Critical hourly mart DQ check failures: {error_message}"
        )

        raise ValueError(
            f"Critical hourly mart DQ checks failed: {error_message}"
        )

    logger.info(
        f"All hourly mart DQ checks executed successfully for window "
        f"[{target_hour_start} to {target_hour_end}]."
    )