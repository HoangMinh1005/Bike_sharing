from src.common.db import fetch_all, fetch_one
from src.common.logger import get_logger
from src.quality.metadata_checks import write_dq_result
from src.services.metadata_refresh_service import refresh_gbfs_station_metadata

logger = get_logger(__name__)

# Controlled self-healing thresholds for metadata drift
AUTO_REFRESH_MAX_UNMAPPED_COUNT = 5
AUTO_REFRESH_MAX_UNMAPPED_RATE = 0.002  # 0.2% max acceptable rate


def run_station_status_dq_checks(run_id: str, batch_id: str) -> None:
    """
    Run data quality checks for station_status raw and staging layers.

    This function checks:
    - raw.station_status_snapshots
    - staging.station_status
    - staging.station_vehicle_type_status

    Critical checks will raise ValueError and fail the Airflow task.
    Warning checks will be recorded but will not fail the pipeline.
    """
    logger.info(
        f"Running station_status data quality checks. "
        f"run_id={run_id} | batch_id={batch_id}"
    )

    checks = [
        # ==================================================
        # RAW LAYER CHECKS
        # ==================================================
        {
            "table": "raw.station_status_snapshots",
            "name": "raw_station_status_snapshot_exists",
            "sql": """
                SELECT CASE WHEN COUNT(*) = 0 THEN 1 ELSE 0 END AS failed_count
                FROM raw.station_status_snapshots
                WHERE batch_id = :batch_id
            """,
            "severity": "CRITICAL",
            "msg_template": "Batch {batch_id}: raw station_status snapshot is empty.",
        },
        {
            "table": "raw.station_status_snapshots",
            "name": "raw_station_status_station_id_not_null_or_empty",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM raw.station_status_snapshots
                WHERE batch_id = :batch_id
                  AND (
                      station_id IS NULL
                      OR TRIM(station_id) = ''
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} raw record(s) "
                "with NULL or empty station_id."
            ),
        },
        {
            "table": "raw.station_status_snapshots",
            "name": "raw_station_status_payload_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM raw.station_status_snapshots
                WHERE batch_id = :batch_id
                  AND raw_station_status IS NULL
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} raw record(s) "
                "with NULL raw_station_status."
            ),
        },
        {
            "table": "raw.station_status_snapshots",
            "name": "raw_station_status_fetched_at_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM raw.station_status_snapshots
                WHERE batch_id = :batch_id
                  AND fetched_at IS NULL
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} raw record(s) "
                "with NULL fetched_at."
            ),
        },
        {
            "table": "raw.station_status_snapshots",
            "name": "raw_station_status_source_last_updated_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM raw.station_status_snapshots
                WHERE batch_id = :batch_id
                  AND source_last_updated IS NULL
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} raw record(s) "
                "with NULL source_last_updated."
            ),
        },
        {
            "table": "raw.station_status_snapshots",
            "name": "raw_station_status_unique_station_in_batch",
            "sql": """
                SELECT COALESCE(SUM(duplicate_count - 1), 0) AS failed_count
                FROM (
                    SELECT station_id, batch_id, COUNT(*) AS duplicate_count
                    FROM raw.station_status_snapshots
                    WHERE batch_id = :batch_id
                    GROUP BY station_id, batch_id
                    HAVING COUNT(*) > 1
                ) dup
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} duplicate raw station_status "
                "record(s) by station_id + batch_id."
            ),
        },

        # ==================================================
        # STAGING.STATION_STATUS COMPLETENESS CHECKS
        # ==================================================
        {
            "table": "staging.station_status",
            "name": "staging_station_status_not_empty",
            "sql": """
                SELECT CASE WHEN COUNT(*) = 0 THEN 1 ELSE 0 END AS failed_count
                FROM staging.station_status
                WHERE batch_id = :batch_id
            """,
            "severity": "CRITICAL",
            "msg_template": "Batch {batch_id}: staging.station_status is empty.",
        },
        {
            "table": "staging.station_status",
            "name": "station_status_raw_to_staging_count_match",
            "sql": """
                WITH raw_count AS (
                    SELECT COUNT(*) AS cnt
                    FROM raw.station_status_snapshots
                    WHERE batch_id = :batch_id
                ),
                staging_count AS (
                    SELECT COUNT(*) AS cnt
                    FROM staging.station_status
                    WHERE batch_id = :batch_id
                )
                SELECT
                    CASE
                        WHEN raw_count.cnt = staging_count.cnt THEN 0
                        ELSE ABS(raw_count.cnt - staging_count.cnt)
                    END AS failed_count
                FROM raw_count, staging_count
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: raw and staging station_status record counts "
                "do not match. Difference: {count} record(s)."
            ),
        },
        {
            "table": "staging.station_status",
            "name": "staging_station_status_unique_station_batch",
            "sql": """
                SELECT COALESCE(SUM(duplicate_count - 1), 0) AS failed_count
                FROM (
                    SELECT station_id, batch_id, COUNT(*) AS duplicate_count
                    FROM staging.station_status
                    WHERE batch_id = :batch_id
                    GROUP BY station_id, batch_id
                    HAVING COUNT(*) > 1
                ) dup
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} duplicate staging station_status "
                "record(s) by station_id + batch_id."
            ),
        },

        # ==================================================
        # STAGING.STATION_STATUS FIELD CHECKS
        # ==================================================
        {
            "table": "staging.station_status",
            "name": "staging_station_status_station_id_not_null_or_empty",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.station_status
                WHERE batch_id = :batch_id
                  AND (
                      station_id IS NULL
                      OR TRIM(station_id) = ''
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} staging record(s) "
                "with NULL or empty station_id."
            ),
        },
        {
            "table": "staging.station_status",
            "name": "staging_station_status_bikes_available_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.station_status
                WHERE batch_id = :batch_id
                  AND num_bikes_available IS NULL
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} record(s) "
                "with NULL num_bikes_available."
            ),
        },
        {
            "table": "staging.station_status",
            "name": "staging_station_status_docks_available_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.station_status
                WHERE batch_id = :batch_id
                  AND num_docks_available IS NULL
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} record(s) "
                "with NULL num_docks_available."
            ),
        },
        {
            "table": "staging.station_status",
            "name": "staging_station_status_bikes_disabled_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.station_status
                WHERE batch_id = :batch_id
                  AND num_bikes_disabled IS NULL
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} record(s) "
                "with NULL num_bikes_disabled."
            ),
        },
        {
            "table": "staging.station_status",
            "name": "staging_station_status_docks_disabled_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.station_status
                WHERE batch_id = :batch_id
                  AND num_docks_disabled IS NULL
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} record(s) "
                "with NULL num_docks_disabled."
            ),
        },
        {
            "table": "staging.station_status",
            "name": "staging_station_status_bikes_available_non_negative",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.station_status
                WHERE batch_id = :batch_id
                  AND num_bikes_available < 0
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} record(s) "
                "with negative num_bikes_available."
            ),
        },
        {
            "table": "staging.station_status",
            "name": "staging_station_status_docks_available_non_negative",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.station_status
                WHERE batch_id = :batch_id
                  AND num_docks_available < 0
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} record(s) "
                "with negative num_docks_available."
            ),
        },
        {
            "table": "staging.station_status",
            "name": "staging_station_status_bikes_disabled_non_negative",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.station_status
                WHERE batch_id = :batch_id
                  AND num_bikes_disabled < 0
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} record(s) "
                "with negative num_bikes_disabled."
            ),
        },
        {
            "table": "staging.station_status",
            "name": "staging_station_status_docks_disabled_non_negative",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.station_status
                WHERE batch_id = :batch_id
                  AND num_docks_disabled < 0
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} record(s) "
                "with negative num_docks_disabled."
            ),
        },
        {
            "table": "staging.station_status",
            "name": "staging_station_status_is_installed_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.station_status
                WHERE batch_id = :batch_id
                  AND is_installed IS NULL
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} record(s) "
                "with NULL is_installed."
            ),
        },
        {
            "table": "staging.station_status",
            "name": "staging_station_status_is_renting_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.station_status
                WHERE batch_id = :batch_id
                  AND is_renting IS NULL
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} record(s) "
                "with NULL is_renting."
            ),
        },
        {
            "table": "staging.station_status",
            "name": "staging_station_status_is_returning_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.station_status
                WHERE batch_id = :batch_id
                  AND is_returning IS NULL
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} record(s) "
                "with NULL is_returning."
            ),
        },
        {
            "table": "staging.station_status",
            "name": "staging_station_status_last_reported_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.station_status
                WHERE batch_id = :batch_id
                  AND last_reported IS NULL
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} record(s) "
                "with NULL last_reported."
            ),
        },
        {
            "table": "staging.station_status",
            "name": "staging_station_status_source_last_updated_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.station_status
                WHERE batch_id = :batch_id
                  AND source_last_updated IS NULL
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} record(s) "
                "with NULL source_last_updated."
            ),
        },
        {
            "table": "staging.station_status",
            "name": "staging_station_status_fetched_at_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.station_status
                WHERE batch_id = :batch_id
                  AND fetched_at IS NULL
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} record(s) "
                "with NULL fetched_at."
            ),
        },

        # ==================================================
        # METADATA MAPPING CHECKS
        # ==================================================
        {
            "table": "staging.station_status",
            "name": "staging_station_status_map_to_stations_metadata",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.station_status ss
                LEFT JOIN staging.stations s
                    ON ss.station_id = s.station_id
                WHERE ss.batch_id = :batch_id
                  AND s.station_id IS NULL
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} station_status record(s) "
                "that do not map to stations metadata."
            ),
        },

        # ==================================================
        # STAGING.STATION_VEHICLE_TYPE_STATUS CHECKS
        # These checks are optional-data-safe.
        # If the table has no records for this batch, they pass.
        # But if records exist, they must be valid.
        # ==================================================
        {
            "table": "staging.station_vehicle_type_status",
            "name": "staging_vehicle_type_status_station_id_not_null_or_empty",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.station_vehicle_type_status
                WHERE batch_id = :batch_id
                  AND (
                      station_id IS NULL
                      OR TRIM(station_id) = ''
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} vehicle type record(s) "
                "with NULL or empty station_id."
            ),
        },
        {
            "table": "staging.station_vehicle_type_status",
            "name": "staging_vehicle_type_status_vehicle_type_id_not_null_or_empty",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.station_vehicle_type_status
                WHERE batch_id = :batch_id
                  AND (
                      vehicle_type_id IS NULL
                      OR TRIM(vehicle_type_id) = ''
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} vehicle type record(s) "
                "with NULL or empty vehicle_type_id."
            ),
        },
        {
            "table": "staging.station_vehicle_type_status",
            "name": "staging_vehicle_type_status_count_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.station_vehicle_type_status
                WHERE batch_id = :batch_id
                  AND count IS NULL
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} vehicle type record(s) "
                "with NULL count."
            ),
        },
        {
            "table": "staging.station_vehicle_type_status",
            "name": "staging_vehicle_type_status_count_non_negative",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.station_vehicle_type_status
                WHERE batch_id = :batch_id
                  AND count < 0
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} vehicle type record(s) "
                "with negative count."
            ),
        },
        {
            "table": "staging.station_vehicle_type_status",
            "name": "staging_vehicle_type_status_unique_station_vehicle_batch",
            "sql": """
                SELECT COALESCE(SUM(duplicate_count - 1), 0) AS failed_count
                FROM (
                    SELECT
                        station_id,
                        vehicle_type_id,
                        batch_id,
                        COUNT(*) AS duplicate_count
                    FROM staging.station_vehicle_type_status
                    WHERE batch_id = :batch_id
                    GROUP BY station_id, vehicle_type_id, batch_id
                    HAVING COUNT(*) > 1
                ) dup
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} duplicate vehicle type status "
                "record(s) by station_id + vehicle_type_id + batch_id."
            ),
        },
    ]

    critical_failures = []

    for check in checks:
        try:
            # Special controlled self-healing handling for metadata mapping check
            if check["name"] == "staging_station_status_map_to_stations_metadata":
                _run_metadata_mapping_check_with_self_healing(
                    run_id=run_id,
                    batch_id=batch_id,
                    check=check,
                    critical_failures=critical_failures,
                )
                continue

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
            f"Critical station_status data quality check failures: "
            f"{error_message}"
        )

        raise ValueError(
            f"Critical station_status DQ checks failed: {error_message}"
        )

    logger.info(
        f"All station_status data quality checks executed successfully "
        f"for batch_id={batch_id}."
    )


def _run_metadata_mapping_check_with_self_healing(
    run_id: str,
    batch_id: str,
    check: dict,
    critical_failures: list,
) -> None:
    """
    Execute staging_station_status_map_to_stations_metadata check with controlled self-healing.

    Flow:
    1. Count total station_status records and unmapped station_status records.
    2. If unmapped_count == 0:
       - PASS. Record DQ result and return.
    3. If unmapped_count > 0 and (unmapped_count <= AUTO_REFRESH_MAX_UNMAPPED_COUNT and rate <= AUTO_REFRESH_MAX_UNMAPPED_RATE):
       - Log metadata drift detection.
       - Trigger controlled inline refresh: refresh_gbfs_station_metadata(batch_id=batch_id, reason="metadata_drift_self_healing").
       - Re-check unmapped count.
       - If new_unmapped_count == 0:
         - PASS_SELF_HEALED. Record DQ result. Do NOT fail pipeline or trigger Telegram error alert.
       - Else:
         - FAIL. Record DQ result and append to critical_failures.
    4. If unmapped_count > AUTO_REFRESH_MAX_UNMAPPED_COUNT or rate > AUTO_REFRESH_MAX_UNMAPPED_RATE:
       - FAIL (exceeds threshold, no auto self-heal). Record DQ result and append to critical_failures.
    """
    total_row = fetch_one(
        "SELECT COUNT(*) AS cnt FROM staging.station_status WHERE batch_id = :batch_id",
        {"batch_id": batch_id},
    )
    total_count = int(total_row["cnt"] or 0) if total_row else 0

    unmapped_rows = fetch_all(
        """
        SELECT ss.station_id
        FROM staging.station_status ss
        LEFT JOIN staging.stations s
            ON ss.station_id = s.station_id
        WHERE ss.batch_id = :batch_id
          AND s.station_id IS NULL
        """,
        {"batch_id": batch_id},
    )
    unmapped_count = len(unmapped_rows)
    unmapped_ids = [r["station_id"] for r in unmapped_rows[:5]]
    unmapped_rate = (unmapped_count / total_count) if total_count > 0 else 0.0

    if unmapped_count == 0:
        message = f"Batch {batch_id}: All station_status records map to stations metadata."
        logger.info(f"DQ Check PASSED: {check['name']} on {check['table']}")
        write_dq_result(
            run_id=run_id,
            table_name=check["table"],
            check_name=check["name"],
            status="passed",
            failed_count=0,
            severity=check["severity"],
            message=message,
        )
        return

    can_self_heal = (
        unmapped_count <= AUTO_REFRESH_MAX_UNMAPPED_COUNT
        and unmapped_rate <= AUTO_REFRESH_MAX_UNMAPPED_RATE
    )

    if can_self_heal:
        logger.warning(
            f"Batch {batch_id}: Detected recoverable metadata drift! "
            f"unmapped_count={unmapped_count}, unmapped_rate={unmapped_rate:.4f}, "
            f"sample_unmapped_ids={unmapped_ids}. "
            f"Attempting controlled inline metadata refresh..."
        )

        try:
            refresh_result = refresh_gbfs_station_metadata(
                batch_id=batch_id,
                reason="metadata_drift_self_healing",
            )
            logger.info(
                f"Batch {batch_id}: Metadata refresh finished. "
                f"result={refresh_result}"
            )

            recheck_rows = fetch_all(
                """
                SELECT ss.station_id
                FROM staging.station_status ss
                LEFT JOIN staging.stations s
                    ON ss.station_id = s.station_id
                WHERE ss.batch_id = :batch_id
                  AND s.station_id IS NULL
                """,
                {"batch_id": batch_id},
            )
            new_unmapped_count = len(recheck_rows)
            new_unmapped_ids = [r["station_id"] for r in recheck_rows[:5]]

            if new_unmapped_count == 0:
                message = (
                    f"Batch {batch_id}: Self-healed {unmapped_count} unmapped station_status record(s) "
                    f"({unmapped_ids}) after refreshing metadata."
                )
                logger.info(
                    f"DQ Check PASSED (SELF_HEALED): {check['name']} on {check['table']} - {message}"
                )
                write_dq_result(
                    run_id=run_id,
                    table_name=check["table"],
                    check_name=check["name"],
                    status="passed",
                    failed_count=0,
                    severity=check["severity"],
                    message=message,
                )
                return
            else:
                message = (
                    f"Batch {batch_id}: Self-healing refresh attempted, but {new_unmapped_count} "
                    f"record(s) ({new_unmapped_ids}) remain unmapped."
                )
                failed_count = new_unmapped_count

        except Exception as refresh_err:
            logger.error(
                f"Batch {batch_id}: Error during controlled metadata refresh: {refresh_err}"
            )
            message = (
                f"Batch {batch_id}: Controlled metadata refresh failed: {refresh_err}. "
                f"Original unmapped count: {unmapped_count}."
            )
            failed_count = unmapped_count

    else:
        message = (
            f"Batch {batch_id}: Found {unmapped_count} unmapped station_status record(s) "
            f"({unmapped_ids}, rate: {unmapped_rate:.4f}), which exceeds self-healing threshold "
            f"(max_count={AUTO_REFRESH_MAX_UNMAPPED_COUNT}, max_rate={AUTO_REFRESH_MAX_UNMAPPED_RATE})."
        )
        failed_count = unmapped_count

    logger.error(f"DQ Check FAILED: {check['name']} on {check['table']} - {message}")
    critical_failures.append(f"{check['name']}: {message}")
    write_dq_result(
        run_id=run_id,
        table_name=check["table"],
        check_name=check["name"],
        status="failed",
        failed_count=failed_count,
        severity=check["severity"],
        message=message,
    )