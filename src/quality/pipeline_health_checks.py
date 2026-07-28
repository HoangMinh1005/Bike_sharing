from src.common.db import fetch_one
from src.common.logger import get_logger
from src.monitoring.pipeline_health_builder import get_monitored_pipelines
from src.quality.metadata_checks import write_dq_result

logger = get_logger(__name__)


def run_pipeline_health_dq_checks(
    run_id: str,
    batch_id: str,
) -> None:
    """
    Run data quality checks for etl_metadata.pipeline_health_summary.

    Critical structural failures raise ValueError and fail pipeline_health_dag.

    Operational health statuses of monitored pipelines:
    - FAILED
    - STALE
    - WARNING
    - UNKNOWN

    are written as WARNING DQ results and do not fail pipeline_health_dag.
    This is intentional because pipeline_health_dag should still succeed
    when it successfully reports that another pipeline is unhealthy.
    """
    expected_pipeline_count = len(get_monitored_pipelines())

    logger.info(
        f"Running pipeline health data quality checks. "
        f"health_run_id={run_id}, "
        f"batch_id={batch_id}, "
        f"expected_pipeline_count={expected_pipeline_count}"
    )

    params = {
        "run_id": run_id,
        "expected_pipeline_count": expected_pipeline_count,
    }

    checks = [
        # ==================================================
        # CRITICAL CHECKS: Structure & Data Integrity
        # ==================================================
        {
            "table": "etl_metadata.pipeline_health_summary",
            "name": "pipeline_health_summary_not_empty",
            "sql": """
                SELECT CASE WHEN COUNT(*) = 0 THEN 1 ELSE 0 END AS failed_count
                FROM etl_metadata.pipeline_health_summary
                WHERE health_run_id = :run_id
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Health run {run_id}: etl_metadata.pipeline_health_summary is empty."
            ),
        },
        {
            "table": "etl_metadata.pipeline_health_summary",
            "name": "pipeline_health_summary_expected_pipeline_count",
            "sql": """
                SELECT
                    CASE
                        WHEN COUNT(*) != CAST(:expected_pipeline_count AS INTEGER)
                        THEN ABS(COUNT(*) - CAST(:expected_pipeline_count AS INTEGER))
                        ELSE 0
                    END AS failed_count
                FROM etl_metadata.pipeline_health_summary
                WHERE health_run_id = :run_id
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Health run {run_id}: pipeline_health_summary row count does not "
                "match expected monitored pipeline count. "
                "Expected {expected_count} monitored pipeline row(s). "
                "Difference={count}."
            ),
        },
        {
            "table": "etl_metadata.pipeline_health_summary",
            "name": "pipeline_health_summary_checked_at_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM etl_metadata.pipeline_health_summary
                WHERE health_run_id = :run_id
                  AND checked_at IS NULL
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Health run {run_id}: Found {count} record(s) with NULL checked_at."
            ),
        },
        {
            "table": "etl_metadata.pipeline_health_summary",
            "name": "pipeline_health_summary_monitored_dag_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM etl_metadata.pipeline_health_summary
                WHERE health_run_id = :run_id
                  AND (
                      monitored_dag_id IS NULL
                      OR TRIM(CAST(monitored_dag_id AS TEXT)) = ''
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Health run {run_id}: Found {count} record(s) with NULL or empty "
                "monitored_dag_id."
            ),
        },
        {
            "table": "etl_metadata.pipeline_health_summary",
            "name": "pipeline_health_summary_pipeline_type_not_null",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM etl_metadata.pipeline_health_summary
                WHERE health_run_id = :run_id
                  AND (
                      pipeline_type IS NULL
                      OR TRIM(CAST(pipeline_type AS TEXT)) = ''
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Health run {run_id}: Found {count} record(s) with NULL or empty "
                "pipeline_type."
            ),
        },
        {
            "table": "etl_metadata.pipeline_health_summary",
            "name": "pipeline_health_summary_status_valid",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM etl_metadata.pipeline_health_summary
                WHERE health_run_id = :run_id
                  AND (
                      health_status IS NULL
                      OR health_status NOT IN (
                          'HEALTHY',
                          'WARNING',
                          'FAILED',
                          'STALE',
                          'UNKNOWN'
                      )
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Health run {run_id}: Found {count} record(s) with invalid "
                "health_status value."
            ),
        },
        {
            "table": "etl_metadata.pipeline_health_summary",
            "name": "pipeline_health_summary_unique_health_run_dag",
            "sql": """
                SELECT COALESCE(SUM(duplicate_count - 1), 0) AS failed_count
                FROM (
                    SELECT
                        health_run_id,
                        monitored_dag_id,
                        COUNT(*) AS duplicate_count
                    FROM etl_metadata.pipeline_health_summary
                    WHERE health_run_id = :run_id
                    GROUP BY
                        health_run_id,
                        monitored_dag_id
                    HAVING COUNT(*) > 1
                ) dup
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Health run {run_id}: Found {count} duplicate health summary "
                "record(s) by health_run_id + monitored_dag_id."
            ),
        },
        {
            "table": "etl_metadata.pipeline_health_summary",
            "name": "pipeline_health_summary_freshness_lag_valid",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM etl_metadata.pipeline_health_summary
                WHERE health_run_id = :run_id
                  AND freshness_lag_minutes IS NOT NULL
                  AND freshness_lag_minutes < 0
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Health run {run_id}: Found {count} record(s) with negative "
                "freshness_lag_minutes."
            ),
        },
        {
            "table": "etl_metadata.pipeline_health_summary",
            "name": "pipeline_health_summary_threshold_valid",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM etl_metadata.pipeline_health_summary
                WHERE health_run_id = :run_id
                  AND (
                      freshness_threshold_minutes IS NULL
                      OR freshness_threshold_minutes <= 0
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Health run {run_id}: Found {count} record(s) with invalid "
                "freshness_threshold_minutes."
            ),
        },
        {
            "table": "etl_metadata.pipeline_health_summary",
            "name": "pipeline_health_summary_count_metrics_valid",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM etl_metadata.pipeline_health_summary
                WHERE health_run_id = :run_id
                  AND (
                      dq_total_checks IS NULL
                      OR dq_total_checks < 0

                      OR dq_failed_checks IS NULL
                      OR dq_failed_checks < 0

                      OR dq_warning_checks IS NULL
                      OR dq_warning_checks < 0

                      OR dq_critical_failed_checks IS NULL
                      OR dq_critical_failed_checks < 0

                      OR rejected_record_count IS NULL
                      OR rejected_record_count < 0

                      OR dq_failed_checks > dq_total_checks
                      OR dq_warning_checks > dq_failed_checks
                      OR dq_critical_failed_checks > dq_failed_checks
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Health run {run_id}: Found {count} record(s) with invalid "
                "count metrics."
            ),
        },

        # ==================================================
        # WARNING CHECKS: Monitored Pipeline Operational Alerts
        # ==================================================
        {
            "table": "etl_metadata.pipeline_health_summary",
            "name": "pipeline_health_summary_unknown_pipeline",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM etl_metadata.pipeline_health_summary
                WHERE health_run_id = :run_id
                  AND health_status = 'UNKNOWN'
            """,
            "severity": "WARNING",
            "msg_template": (
                "Health run {run_id}: Found {count} monitored pipeline(s) "
                "with UNKNOWN status."
            ),
        },
        {
            "table": "etl_metadata.pipeline_health_summary",
            "name": "pipeline_health_summary_failed_pipeline",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM etl_metadata.pipeline_health_summary
                WHERE health_run_id = :run_id
                  AND health_status = 'FAILED'
            """,
            "severity": "WARNING",
            "msg_template": (
                "Health run {run_id}: Found {count} monitored pipeline(s) "
                "with FAILED status."
            ),
        },
        {
            "table": "etl_metadata.pipeline_health_summary",
            "name": "pipeline_health_summary_stale_pipeline",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM etl_metadata.pipeline_health_summary
                WHERE health_run_id = :run_id
                  AND health_status = 'STALE'
            """,
            "severity": "WARNING",
            "msg_template": (
                "Health run {run_id}: Found {count} monitored pipeline(s) "
                "with STALE status."
            ),
        },
        {
            "table": "etl_metadata.pipeline_health_summary",
            "name": "pipeline_health_summary_warning_pipeline",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM etl_metadata.pipeline_health_summary
                WHERE health_run_id = :run_id
                  AND health_status = 'WARNING'
            """,
            "severity": "WARNING",
            "msg_template": (
                "Health run {run_id}: Found {count} monitored pipeline(s) "
                "with WARNING status."
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
                    run_id=run_id,
                    count=failed_count,
                    expected_count=expected_pipeline_count,
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
                    f"Health run {run_id}: All records passed check."
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
            f"Critical pipeline health DQ check failures: {error_message}"
        )

        raise ValueError(
            f"Critical pipeline health DQ checks failed: {error_message}"
        )

    logger.info(
        f"All pipeline health DQ checks executed successfully for "
        f"health_run_id={run_id}."
    )