import pendulum
from typing import Any, Dict, List, Optional

from src.common.db import execute_sql, fetch_one
from src.common.logger import get_logger

logger = get_logger(__name__)


MONITORED_PIPELINES: List[Dict[str, Any]] = [
    {
        "dag_id": "gbfs_metadata_daily_dag",
        "pipeline_type": "metadata",
        "expected_schedule": "daily",
        "freshness_threshold_minutes": 36 * 60,
        "watermark_source_name": "gbfs_metadata",
    },
    {
        "dag_id": "station_status_snapshot_dag",
        "pipeline_type": "snapshot",
        "expected_schedule": "every_15_minutes",
        "freshness_threshold_minutes": 60,
        "watermark_source_name": "gbfs_station_status",
    },
    {
        "dag_id": "weather_calendar_sync_dag",
        "pipeline_type": "enrichment",
        "expected_schedule": "every_3_hours",
        "freshness_threshold_minutes": 6 * 60,
        "watermark_source_name": "weather_hourly",
    },
    {
        "dag_id": "hourly_mart_build_dag",
        "pipeline_type": "hourly_mart",
        "expected_schedule": "hourly",
        "freshness_threshold_minutes": 3 * 60,
        "watermark_source_name": "hourly_mart",
    },
    {
        "dag_id": "daily_summary_dag",
        "pipeline_type": "daily_mart",
        "expected_schedule": "daily",
        "freshness_threshold_minutes": 36 * 60,
        "watermark_source_name": "daily_summary",
    },
]


def get_monitored_pipelines() -> List[Dict[str, Any]]:
    """
    Return configured list of monitored pipelines.

    Return a copied list to avoid accidental mutation from caller code.
    """
    return [dict(pipeline) for pipeline in MONITORED_PIPELINES]


def _to_pendulum_datetime(
    value: Any,
    use_now_when_none: bool = False,
) -> Optional[pendulum.DateTime]:
    """
    Normalize a datetime-like value to pendulum DateTime in UTC.

    Supports:
    - None
    - str
    - datetime.datetime
    - pendulum.DateTime

    If value is None:
    - return current UTC time if use_now_when_none=True
    - otherwise return None
    """
    if value is None:
        if use_now_when_none:
            return pendulum.now("UTC")
        return None

    try:
        if isinstance(value, pendulum.DateTime):
            dt = value
        elif isinstance(value, str):
            dt = pendulum.parse(value)
        else:
            dt = pendulum.instance(value)

        if getattr(dt, "tzinfo", None) is None:
            dt = dt.replace(tzinfo=pendulum.timezone("UTC"))
        else:
            dt = dt.in_timezone("UTC")

        return dt

    except Exception as e:
        raise ValueError(f"Cannot parse datetime value '{value}'. error={e}") from e


def _to_db_timestamp_string(value: Any) -> Optional[str]:
    """
    Convert datetime-like value to PostgreSQL-friendly timestamp string.

    Return format:
        YYYY-MM-DD HH:mm:ss

    Return None if input is None.
    """
    dt = _to_pendulum_datetime(value)
    if dt is None:
        return None
    return dt.to_datetime_string()


def _safe_int(value: Any) -> Optional[int]:
    """Convert value to int safely, preserving None."""
    if value is None:
        return None
    return int(value)


def _safe_float(value: Any) -> Optional[float]:
    """Convert value to float safely, preserving None."""
    if value is None:
        return None
    return float(value)


def _validate_health_run_inputs(
    health_run_id: str,
    batch_id: str,
    checked_at: str,
) -> None:
    """
    Validate input parameters for pipeline health summary build.
    """
    if not health_run_id or not str(health_run_id).strip():
        raise ValueError("health_run_id cannot be empty")

    if not batch_id or not str(batch_id).strip():
        raise ValueError("batch_id cannot be empty")

    try:
        _to_pendulum_datetime(checked_at)
    except Exception as e:
        raise ValueError(
            f"Invalid checked_at datetime format: '{checked_at}'. error={e}"
        ) from e


def _validate_pipeline_config(pipeline: Dict[str, Any]) -> None:
    """
    Validate a monitored pipeline config.
    """
    required_fields = [
        "dag_id",
        "pipeline_type",
        "expected_schedule",
        "freshness_threshold_minutes",
        "watermark_source_name",
    ]

    for field in required_fields:
        value = pipeline.get(field)
        if value is None or str(value).strip() == "":
            raise ValueError(
                f"Invalid monitored pipeline config. "
                f"Missing or empty field='{field}', pipeline={pipeline}"
            )

    threshold = int(pipeline["freshness_threshold_minutes"])
    if threshold <= 0:
        raise ValueError(
            f"freshness_threshold_minutes must be > 0. pipeline={pipeline}"
        )


def build_pipeline_health_summary(
    health_run_id: str,
    batch_id: str,
    checked_at: Optional[str] = None,
) -> int:
    """
    Build health status summary for all monitored ETL pipelines and store
    results into etl_metadata.pipeline_health_summary.

    Grain:
        1 row / health_run_id / monitored_dag_id

    Health status meaning:
    - HEALTHY: latest run succeeded, freshness is within threshold, no warnings.
    - WARNING: latest run succeeded but has warning signs, such as DQ warnings,
      rejected records, 0 records loaded, or unavailable freshness timestamp.
    - FAILED: latest run failed or latest run has critical DQ failures.
    - STALE: latest successful run is older than freshness threshold.
    - UNKNOWN: no pipeline run found.

    Important:
        This function should not raise just because a monitored pipeline is
        FAILED, STALE, WARNING, or UNKNOWN. Those are valid health states.
        It should only raise if the health summary itself cannot be built.

    Returns:
        Number of monitored pipeline rows inserted/upserted.
    """
    checked_at_dt = _to_pendulum_datetime(
        checked_at,
        use_now_when_none=True,
    )
    checked_at_str = checked_at_dt.to_datetime_string()

    _validate_health_run_inputs(
        health_run_id=health_run_id,
        batch_id=batch_id,
        checked_at=checked_at_str,
    )

    logger.info(
        f"Building pipeline health summary for health_run_id={health_run_id}, "
        f"batch_id={batch_id}, checked_at={checked_at_str}"
    )

    inserted_count = 0

    for pipeline in get_monitored_pipelines():
        _validate_pipeline_config(pipeline)

        dag_id = pipeline["dag_id"]
        pipeline_type = pipeline["pipeline_type"]
        expected_schedule = pipeline["expected_schedule"]
        freshness_threshold = int(pipeline["freshness_threshold_minutes"])
        watermark_source_name = pipeline["watermark_source_name"]

        logger.info(
            f"Building health row for monitored DAG '{dag_id}' "
            f"with watermark_source_name='{watermark_source_name}'"
        )

        # 1. Latest pipeline run
        latest_run = fetch_one(
            """
            SELECT
                run_id,
                dag_id,
                status,
                started_at,
                ended_at,
                duration_seconds,
                records_extracted,
                records_loaded,
                records_rejected
            FROM etl_metadata.pipeline_runs
            WHERE dag_id = :dag_id
            ORDER BY started_at DESC NULLS LAST
            LIMIT 1
            """,
            {"dag_id": dag_id},
        )

        # 2. Latest successful pipeline run
        latest_success = fetch_one(
            """
            SELECT
                run_id,
                ended_at,
                started_at
            FROM etl_metadata.pipeline_runs
            WHERE dag_id = :dag_id
              AND status = 'success'
            ORDER BY ended_at DESC NULLS LAST, started_at DESC NULLS LAST
            LIMIT 1
            """,
            {"dag_id": dag_id},
        )

        # 3. Watermark entry
        watermark = fetch_one(
            """
            SELECT
                last_successful_value,
                updated_at
            FROM etl_metadata.watermarks
            WHERE source_name = :source_name
            ORDER BY updated_at DESC NULLS LAST
            LIMIT 1
            """,
            {"source_name": watermark_source_name},
        )

        # 4. Extract latest run details
        latest_run_id = latest_run["run_id"] if latest_run else None
        latest_run_status = latest_run["status"] if latest_run else None
        latest_run_status_normalized = (
            str(latest_run_status).lower()
            if latest_run_status is not None
            else None
        )

        latest_started_at = (
            _to_pendulum_datetime(latest_run["started_at"])
            if latest_run and latest_run["started_at"] is not None
            else None
        )

        latest_finished_at = (
            _to_pendulum_datetime(latest_run["ended_at"])
            if latest_run and latest_run["ended_at"] is not None
            else None
        )

        latest_duration_seconds = (
            _safe_float(latest_run["duration_seconds"])
            if latest_run
            else None
        )

        latest_records_extracted = (
            _safe_int(latest_run["records_extracted"])
            if latest_run
            else None
        )

        latest_records_loaded = (
            _safe_int(latest_run["records_loaded"])
            if latest_run
            else None
        )

        latest_records_rejected = (
            _safe_int(latest_run["records_rejected"])
            if latest_run
            else None
        )

        # 5. Extract latest success details
        latest_success_run_id = (
            latest_success["run_id"]
            if latest_success
            else None
        )

        latest_success_finished_at = None

        if latest_success:
            if latest_success["ended_at"] is not None:
                latest_success_finished_at = _to_pendulum_datetime(
                    latest_success["ended_at"]
                )
            elif latest_success["started_at"] is not None:
                latest_success_finished_at = _to_pendulum_datetime(
                    latest_success["started_at"]
                )

        # 6. Extract watermark details
        watermark_value = (
            watermark["last_successful_value"]
            if watermark
            else None
        )

        watermark_updated_at = (
            _to_pendulum_datetime(watermark["updated_at"])
            if watermark and watermark["updated_at"] is not None
            else None
        )

        # 7. Calculate freshness lag minutes
        #
        # Priority:
        # 1. latest_success_finished_at
        # 2. watermark_updated_at
        #
        # If neither exists, freshness_lag_minutes remains None.
        base_time = latest_success_finished_at or watermark_updated_at

        freshness_lag_minutes = None
        if base_time is not None:
            lag_seconds = (checked_at_dt - base_time).total_seconds()
            freshness_lag_minutes = max(
                0.0,
                round(lag_seconds / 60.0, 2),
            )

        # 8. DQ summary for latest_run_id
        dq_total_checks = 0
        dq_failed_checks = 0
        dq_warning_checks = 0
        dq_critical_failed_checks = 0

        if latest_run_id:
            dq_res = fetch_one(
                """
                SELECT
                    COUNT(*) AS dq_total_checks,
                    COUNT(CASE WHEN status IN ('failed', 'warning') THEN 1 END) AS dq_failed_checks,
                    COUNT(
                        CASE
                            WHEN status = 'warning'
                              OR (status = 'failed' AND severity = 'WARNING')
                            THEN 1
                        END
                    ) AS dq_warning_checks,
                    COUNT(
                        CASE
                            WHEN status = 'failed'
                              AND severity = 'CRITICAL'
                            THEN 1
                        END
                    ) AS dq_critical_failed_checks
                FROM etl_metadata.dq_results
                WHERE run_id = :run_id
                """,
                {"run_id": latest_run_id},
            )

            if dq_res:
                dq_total_checks = int(dq_res["dq_total_checks"] or 0)
                dq_failed_checks = int(dq_res["dq_failed_checks"] or 0)
                dq_warning_checks = int(dq_res["dq_warning_checks"] or 0)
                dq_critical_failed_checks = int(
                    dq_res["dq_critical_failed_checks"] or 0
                )

        # 9. Rejected record count for latest_run_id
        rejected_record_count = 0

        if latest_run_id:
            rejected_res = fetch_one(
                """
                SELECT COUNT(*) AS rejected_count
                FROM etl_metadata.rejected_records
                WHERE run_id = :run_id
                """,
                {"run_id": latest_run_id},
            )

            rejected_from_table = (
                int(rejected_res["rejected_count"] or 0)
                if rejected_res
                else 0
            )

            rejected_from_pipeline_run = int(latest_records_rejected or 0)

            rejected_record_count = max(
                rejected_from_table,
                rejected_from_pipeline_run,
            )

        # 10. Health status logic
        if latest_run is None:
            health_status = "UNKNOWN"
            health_message = "No pipeline run found."

        elif (
            latest_run_status_normalized != "success"
            or dq_critical_failed_checks > 0
        ):
            health_status = "FAILED"

            if latest_run_status_normalized != "success":
                health_message = (
                    f"Latest run status is '{latest_run_status}'."
                )
            else:
                health_message = (
                    f"Latest run completed with "
                    f"{dq_critical_failed_checks} critical DQ check failure(s)."
                )

        elif freshness_lag_minutes is None:
            health_status = "WARNING"
            health_message = (
                "Pipeline succeeded but freshness timestamp is unavailable."
            )

        elif freshness_lag_minutes > freshness_threshold:
            health_status = "STALE"
            health_message = (
                f"Pipeline is stale. "
                f"freshness_lag_minutes={freshness_lag_minutes:.1f}, "
                f"threshold={freshness_threshold}."
            )

        elif (
            dq_warning_checks > 0
            or rejected_record_count > 0
            or (
                latest_records_loaded is not None
                and latest_records_loaded == 0
            )
        ):
            health_status = "WARNING"

            warnings = []

            if dq_warning_checks > 0:
                warnings.append(
                    f"{dq_warning_checks} DQ warning check(s)"
                )

            if rejected_record_count > 0:
                warnings.append(
                    f"{rejected_record_count} rejected record(s)"
                )

            if (
                latest_records_loaded is not None
                and latest_records_loaded == 0
            ):
                warnings.append("0 records loaded")

            health_message = (
                f"Pipeline completed with warnings: "
                f"{', '.join(warnings)}."
            )

        else:
            health_status = "HEALTHY"
            health_message = "Pipeline is healthy."

        # 11. Upsert health summary row
        upsert_sql = """
            INSERT INTO etl_metadata.pipeline_health_summary (
                health_run_id,
                batch_id,
                checked_at,
                monitored_dag_id,
                pipeline_type,
                expected_schedule,
                freshness_threshold_minutes,
                latest_run_id,
                latest_run_status,
                latest_started_at,
                latest_finished_at,
                latest_duration_seconds,
                latest_records_extracted,
                latest_records_loaded,
                latest_records_rejected,
                latest_success_run_id,
                latest_success_finished_at,
                watermark_source_name,
                watermark_value,
                watermark_updated_at,
                freshness_lag_minutes,
                dq_total_checks,
                dq_failed_checks,
                dq_warning_checks,
                dq_critical_failed_checks,
                rejected_record_count,
                health_status,
                health_message,
                updated_at
            ) VALUES (
                :health_run_id,
                :batch_id,
                CAST(:checked_at AS TIMESTAMP),
                :monitored_dag_id,
                :pipeline_type,
                :expected_schedule,
                :freshness_threshold_minutes,
                :latest_run_id,
                :latest_run_status,
                CAST(:latest_started_at AS TIMESTAMP),
                CAST(:latest_finished_at AS TIMESTAMP),
                :latest_duration_seconds,
                :latest_records_extracted,
                :latest_records_loaded,
                :latest_records_rejected,
                :latest_success_run_id,
                CAST(:latest_success_finished_at AS TIMESTAMP),
                :watermark_source_name,
                :watermark_value,
                CAST(:watermark_updated_at AS TIMESTAMP),
                :freshness_lag_minutes,
                :dq_total_checks,
                :dq_failed_checks,
                :dq_warning_checks,
                :dq_critical_failed_checks,
                :rejected_record_count,
                :health_status,
                :health_message,
                CURRENT_TIMESTAMP
            )
            ON CONFLICT (health_run_id, monitored_dag_id) DO UPDATE SET
                batch_id = EXCLUDED.batch_id,
                checked_at = EXCLUDED.checked_at,
                pipeline_type = EXCLUDED.pipeline_type,
                expected_schedule = EXCLUDED.expected_schedule,
                freshness_threshold_minutes = EXCLUDED.freshness_threshold_minutes,
                latest_run_id = EXCLUDED.latest_run_id,
                latest_run_status = EXCLUDED.latest_run_status,
                latest_started_at = EXCLUDED.latest_started_at,
                latest_finished_at = EXCLUDED.latest_finished_at,
                latest_duration_seconds = EXCLUDED.latest_duration_seconds,
                latest_records_extracted = EXCLUDED.latest_records_extracted,
                latest_records_loaded = EXCLUDED.latest_records_loaded,
                latest_records_rejected = EXCLUDED.latest_records_rejected,
                latest_success_run_id = EXCLUDED.latest_success_run_id,
                latest_success_finished_at = EXCLUDED.latest_success_finished_at,
                watermark_source_name = EXCLUDED.watermark_source_name,
                watermark_value = EXCLUDED.watermark_value,
                watermark_updated_at = EXCLUDED.watermark_updated_at,
                freshness_lag_minutes = EXCLUDED.freshness_lag_minutes,
                dq_total_checks = EXCLUDED.dq_total_checks,
                dq_failed_checks = EXCLUDED.dq_failed_checks,
                dq_warning_checks = EXCLUDED.dq_warning_checks,
                dq_critical_failed_checks = EXCLUDED.dq_critical_failed_checks,
                rejected_record_count = EXCLUDED.rejected_record_count,
                health_status = EXCLUDED.health_status,
                health_message = EXCLUDED.health_message,
                updated_at = CURRENT_TIMESTAMP
        """

        params = {
            "health_run_id": health_run_id,
            "batch_id": batch_id,
            "checked_at": checked_at_str,
            "monitored_dag_id": dag_id,
            "pipeline_type": pipeline_type,
            "expected_schedule": expected_schedule,
            "freshness_threshold_minutes": freshness_threshold,
            "latest_run_id": latest_run_id,
            "latest_run_status": latest_run_status,
            "latest_started_at": _to_db_timestamp_string(latest_started_at),
            "latest_finished_at": _to_db_timestamp_string(latest_finished_at),
            "latest_duration_seconds": latest_duration_seconds,
            "latest_records_extracted": latest_records_extracted,
            "latest_records_loaded": latest_records_loaded,
            "latest_records_rejected": latest_records_rejected,
            "latest_success_run_id": latest_success_run_id,
            "latest_success_finished_at": _to_db_timestamp_string(
                latest_success_finished_at
            ),
            "watermark_source_name": watermark_source_name,
            "watermark_value": watermark_value,
            "watermark_updated_at": _to_db_timestamp_string(
                watermark_updated_at
            ),
            "freshness_lag_minutes": freshness_lag_minutes,
            "dq_total_checks": dq_total_checks,
            "dq_failed_checks": dq_failed_checks,
            "dq_warning_checks": dq_warning_checks,
            "dq_critical_failed_checks": dq_critical_failed_checks,
            "rejected_record_count": rejected_record_count,
            "health_status": health_status,
            "health_message": health_message,
        }

        execute_sql(upsert_sql, params)

        # One monitored pipeline should produce exactly one health summary row.
        inserted_count += 1

        logger.info(
            f"Health summary updated for DAG '{dag_id}': "
            f"status='{health_status}', "
            f"lag={freshness_lag_minutes}m, "
            f"message='{health_message}'"
        )

    logger.info(
        f"Pipeline health summary build completed for "
        f"health_run_id={health_run_id}. "
        f"Total monitored pipelines updated: {inserted_count}"
    )

    return inserted_count