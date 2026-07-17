from typing import Optional

from src.common.db import execute_sql, fetch_one
from src.common.logger import get_logger

logger = get_logger(__name__)


def write_dq_result(
    run_id: str,
    table_name: str,
    check_name: str,
    status: str,
    failed_count: int,
    severity: str,
    message: Optional[str] = None,
) -> None:
    """
    Insert a data quality check result into etl_metadata.dq_results.
    """
    sql = """
        INSERT INTO etl_metadata.dq_results (
            run_id,
            table_name,
            check_name,
            status,
            failed_count,
            severity,
            checked_at,
            message
        ) VALUES (
            :run_id,
            :table_name,
            :check_name,
            :status,
            :failed_count,
            :severity,
            CURRENT_TIMESTAMP,
            :message
        )
    """

    execute_sql(
        sql,
        {
            "run_id": run_id,
            "table_name": table_name,
            "check_name": check_name,
            "status": status,
            "failed_count": failed_count,
            "severity": severity,
            "message": message,
        },
    )


def run_metadata_dq_checks(run_id: str, batch_id: str) -> None:
    """
    Run data quality checks for metadata raw and staging layers.

    Scope:
    - Raw layer checks use raw.gbfs_feed_snapshots.batch_id.
    - Staging layer checks use staging.*.source_batch_id.
    - CRITICAL checks fail the pipeline.
    - WARNING checks are recorded but do not fail the pipeline.
    """
    logger.info(
        f"Running metadata data quality checks. "
        f"run_id={run_id} | batch_id={batch_id}"
    )

    checks = [
        # ==================================================
        # RAW LAYER CHECKS
        # ==================================================
        {
            "table": "raw.gbfs_feed_snapshots",
            "name": "raw_metadata_required_feeds_count",
            "sql": """
                SELECT 4 - COUNT(DISTINCT feed_name) AS failed_count
                FROM raw.gbfs_feed_snapshots
                WHERE batch_id = :batch_id
                  AND feed_name IN (
                      'system_information',
                      'system_regions',
                      'vehicle_types',
                      'station_information'
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Missing {count} required metadata feed(s) "
                "in raw layer."
            ),
        },
        {
            "table": "raw.gbfs_feed_snapshots",
            "name": "raw_metadata_payload_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM raw.gbfs_feed_snapshots
                WHERE batch_id = :batch_id
                  AND feed_name IN (
                      'system_information',
                      'system_regions',
                      'vehicle_types',
                      'station_information'
                  )
                  AND raw_payload IS NULL
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} raw metadata feed(s) "
                "with NULL raw_payload."
            ),
        },
        {
            "table": "raw.gbfs_feed_snapshots",
            "name": "raw_metadata_duplicate_feed_in_batch",
            "sql": """
                SELECT COUNT(*) - COUNT(DISTINCT feed_name) AS failed_count
                FROM raw.gbfs_feed_snapshots
                WHERE batch_id = :batch_id
                  AND feed_name IN (
                      'system_information',
                      'system_regions',
                      'vehicle_types',
                      'station_information'
                  )
            """,
            "severity": "WARNING",
            "msg_template": (
                "Batch {batch_id}: Found {count} duplicate raw metadata "
                "feed record(s) in the same batch."
            ),
        },

        # ==================================================
        # STAGING LAYER COMPLETENESS CHECKS
        # ==================================================
        {
            "table": "staging.system_information",
            "name": "system_information_not_empty",
            "sql": """
                SELECT CASE WHEN COUNT(*) = 0 THEN 1 ELSE 0 END AS failed_count
                FROM staging.system_information
                WHERE source_batch_id = :batch_id
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: staging.system_information is empty."
            ),
        },
        {
            "table": "staging.regions",
            "name": "regions_not_empty",
            "sql": """
                SELECT CASE WHEN COUNT(*) = 0 THEN 1 ELSE 0 END AS failed_count
                FROM staging.regions
                WHERE source_batch_id = :batch_id
            """,
            "severity": "CRITICAL",
            "msg_template": "Batch {batch_id}: staging.regions is empty.",
        },
        {
            "table": "staging.vehicle_types",
            "name": "vehicle_types_not_empty",
            "sql": """
                SELECT CASE WHEN COUNT(*) = 0 THEN 1 ELSE 0 END AS failed_count
                FROM staging.vehicle_types
                WHERE source_batch_id = :batch_id
            """,
            "severity": "CRITICAL",
            "msg_template": "Batch {batch_id}: staging.vehicle_types is empty.",
        },
        {
            "table": "staging.stations",
            "name": "stations_not_empty",
            "sql": """
                SELECT CASE WHEN COUNT(*) = 0 THEN 1 ELSE 0 END AS failed_count
                FROM staging.stations
                WHERE source_batch_id = :batch_id
            """,
            "severity": "CRITICAL",
            "msg_template": "Batch {batch_id}: staging.stations is empty.",
        },

        # ==================================================
        # staging.system_information CHECKS
        # ==================================================
        {
            "table": "staging.system_information",
            "name": "system_information_system_id_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.system_information
                WHERE source_batch_id = :batch_id
                  AND system_id IS NULL
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} system record(s) "
                "with NULL system_id."
            ),
        },
        {
            "table": "staging.system_information",
            "name": "system_information_timezone_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.system_information
                WHERE source_batch_id = :batch_id
                  AND timezone IS NULL
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} system record(s) "
                "with NULL timezone."
            ),
        },

        # ==================================================
        # staging.regions CHECKS
        # ==================================================
        {
            "table": "staging.regions",
            "name": "regions_region_id_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.regions
                WHERE source_batch_id = :batch_id
                  AND region_id IS NULL
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} region record(s) "
                "with NULL region_id."
            ),
        },
        {
            "table": "staging.regions",
            "name": "regions_region_name_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.regions
                WHERE source_batch_id = :batch_id
                  AND region_name IS NULL
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} region record(s) "
                "with NULL region_name."
            ),
        },
        {
            "table": "staging.regions",
            "name": "regions_region_id_unique",
            "sql": """
                SELECT COUNT(*) - COUNT(DISTINCT region_id) AS failed_count
                FROM staging.regions
                WHERE source_batch_id = :batch_id
                  AND region_id IS NOT NULL
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} duplicate region_id record(s)."
            ),
        },

        # ==================================================
        # staging.vehicle_types CHECKS
        # ==================================================
        {
            "table": "staging.vehicle_types",
            "name": "vehicle_types_vehicle_type_id_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.vehicle_types
                WHERE source_batch_id = :batch_id
                  AND vehicle_type_id IS NULL
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} vehicle_type record(s) "
                "with NULL vehicle_type_id."
            ),
        },
        {
            "table": "staging.vehicle_types",
            "name": "vehicle_types_vehicle_type_id_unique",
            "sql": """
                SELECT COUNT(*) - COUNT(DISTINCT vehicle_type_id) AS failed_count
                FROM staging.vehicle_types
                WHERE source_batch_id = :batch_id
                  AND vehicle_type_id IS NOT NULL
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} duplicate vehicle_type_id record(s)."
            ),
        },

        # ==================================================
        # staging.stations CHECKS
        # ==================================================
        {
            "table": "staging.stations",
            "name": "stations_station_id_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.stations
                WHERE source_batch_id = :batch_id
                  AND station_id IS NULL
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} station record(s) "
                "with NULL station_id."
            ),
        },
        {
            "table": "staging.stations",
            "name": "stations_station_name_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.stations
                WHERE source_batch_id = :batch_id
                  AND station_name IS NULL
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} station record(s) "
                "with NULL station_name."
            ),
        },
        {
            "table": "staging.stations",
            "name": "stations_station_id_unique",
            "sql": """
                SELECT COUNT(*) - COUNT(DISTINCT station_id) AS failed_count
                FROM staging.stations
                WHERE source_batch_id = :batch_id
                  AND station_id IS NOT NULL
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} duplicate station_id record(s)."
            ),
        },
        {
            "table": "staging.stations",
            "name": "stations_latitude_valid",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.stations
                WHERE source_batch_id = :batch_id
                  AND (
                      latitude IS NULL
                      OR latitude < -90
                      OR latitude > 90
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} station record(s) "
                "with invalid or NULL latitude."
            ),
        },
        {
            "table": "staging.stations",
            "name": "stations_longitude_valid",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.stations
                WHERE source_batch_id = :batch_id
                  AND (
                      longitude IS NULL
                      OR longitude < -180
                      OR longitude > 180
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} station record(s) "
                "with invalid or NULL longitude."
            ),
        },
        {
            "table": "staging.stations",
            "name": "stations_capacity_non_negative",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.stations
                WHERE source_batch_id = :batch_id
                  AND capacity IS NOT NULL
                  AND capacity < 0
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Batch {batch_id}: Found {count} station record(s) "
                "with negative capacity."
            ),
        },
        {
            "table": "staging.stations",
            "name": "stations_region_id_missing",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM staging.stations
                WHERE source_batch_id = :batch_id
                  AND region_id IS NULL
            """,
            "severity": "WARNING",
            "msg_template": (
                "Batch {batch_id}: Found {count} station record(s) "
                "with NULL region_id."
            ),
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

                if check["severity"] == "CRITICAL":
                    status = "failed"

                    logger.error(
                        f"DQ Check FAILED: {check['name']} "
                        f"on {check['table']} - {message}"
                    )

                    critical_failures.append(
                        f"{check['name']}: {message}"
                    )

                else:
                    status = "warning"

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
            logger.error(
                f"Error executing DQ check '{check['name']}': {e}"
            )

            write_dq_result(
                run_id=run_id,
                table_name=check["table"],
                check_name=check["name"],
                status="failed",
                failed_count=1,
                severity=check["severity"],
                message=f"Batch {batch_id}: Execution error: {e}",
            )

            if check["severity"] == "CRITICAL":
                critical_failures.append(
                    f"{check['name']} execution error: {e}"
                )

    if critical_failures:
        error_message = "; ".join(critical_failures)

        logger.error(
            f"Critical data quality check failures: {error_message}"
        )

        raise ValueError(
            f"Critical DQ checks failed: {error_message}"
        )

    logger.info(
        f"All metadata data quality checks executed successfully "
        f"for batch_id={batch_id}."
    )