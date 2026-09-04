import pendulum

from airflow.decorators import dag, task
from src.common.logger import get_logger
from src.alerts.airflow_callbacks import (
    airflow_task_failure_callback,
    airflow_task_success_callback,
)

logger = get_logger(__name__)


default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 0,
    "on_failure_callback": airflow_task_failure_callback,
    "on_success_callback": airflow_task_success_callback,
}


@dag(
    dag_id="pipeline_health_dag",
    default_args=default_args,
    on_failure_callback=airflow_task_failure_callback,
    description="ETL Pipeline Health & DQ Monitoring DAG",
    schedule="50 * * * *",
    start_date=pendulum.datetime(2026, 7, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    tags=["metadata", "health", "monitoring", "dq", "etl"],
)
def pipeline_health_dag():
    @task
    def start_pipeline() -> dict:
        """
        1. Initialize pipeline run tracking for pipeline_health_dag.
        """
        from airflow.operators.python import get_current_context
        from src.metadata.pipeline_run_tracker import (
            start_pipeline_run,
            finish_pipeline_run_failed,
        )

        context = get_current_context()

        dag_id = context["dag"].dag_id
        run_id = context["run_id"]
        batch_id = run_id
        checked_at = pendulum.now("UTC").to_iso8601_string()

        try:
            logger.info(
                f"Starting pipeline health monitoring run. "
                f"run_id={run_id}, dag_id={dag_id}, checked_at={checked_at}"
            )

            start_pipeline_run(
                run_id=run_id,
                dag_id=dag_id,
            )

            return {
                "run_id": run_id,
                "batch_id": batch_id,
                "dag_id": dag_id,
                "checked_at": checked_at,
            }

        except Exception as e:
            logger.error(f"Error in start_pipeline task: {e}")

            try:
                finish_pipeline_run_failed(
                    run_id=run_id,
                    error_message=f"Start pipeline health tracking failed: {e}",
                )
            except Exception as tracking_error:
                logger.error(
                    f"Could not mark pipeline health run as failed after "
                    f"start error. run_id={run_id}, error={tracking_error}"
                )

            raise

    @task
    def prepare_health_summary_for_rerun(batch_info: dict) -> dict:
        """
        2. Delete existing health summary records for current health_run_id.

        This makes reruns idempotent.
        """
        from src.common.db import execute_sql
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed

        run_id = batch_info["run_id"]

        try:
            logger.info(
                f"Preparing health summary table for health_run_id={run_id}"
            )

            deleted_count = execute_sql(
                """
                DELETE FROM etl_metadata.pipeline_health_summary
                WHERE health_run_id = :health_run_id
                """,
                {"health_run_id": run_id},
            )

            logger.info(
                f"Deleted existing pipeline health summary records. "
                f"health_run_id={run_id}, deleted_count={deleted_count}"
            )

            return batch_info

        except Exception as e:
            logger.error(f"Error in prepare_health_summary_for_rerun task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Prepare health summary for rerun failed: {e}",
            )

            raise

    @task
    def build_health_summary(batch_info: dict) -> dict:
        """
        3. Read metadata tables and compute health status for monitored pipelines.
        """
        from src.monitoring.pipeline_health_builder import (
            build_pipeline_health_summary,
        )
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed

        run_id = batch_info["run_id"]
        batch_id = batch_info["batch_id"]
        checked_at = batch_info["checked_at"]

        try:
            loaded = build_pipeline_health_summary(
                health_run_id=run_id,
                batch_id=batch_id,
                checked_at=checked_at,
            )

            loaded = int(loaded or 0)

            if loaded <= 0:
                raise RuntimeError(
                    f"No records built for "
                    f"etl_metadata.pipeline_health_summary. "
                    f"health_run_id={run_id}"
                )

            logger.info(
                f"Built pipeline health summary. "
                f"health_run_id={run_id}, rows_loaded={loaded}"
            )

            return {
                **batch_info,
                "health_rows_loaded": loaded,
            }

        except Exception as e:
            logger.error(f"Error in build_health_summary task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Build pipeline health summary failed: {e}",
            )

            raise

    @task
    def run_dq(batch_info: dict) -> dict:
        """
        4. Run DQ checks for etl_metadata.pipeline_health_summary.

        Monitored pipelines with FAILED/STALE/WARNING/UNKNOWN status are
        written as warning DQ results. They should not fail pipeline_health_dag.
        """
        from src.quality.pipeline_health_checks import (
            run_pipeline_health_dq_checks,
        )
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed

        run_id = batch_info["run_id"]
        batch_id = batch_info["batch_id"]

        try:
            logger.info(
                f"Running pipeline health DQ checks. health_run_id={run_id}"
            )

            run_pipeline_health_dq_checks(
                run_id=run_id,
                batch_id=batch_id,
            )

            return batch_info

        except Exception as e:
            logger.error(f"Error in run_dq task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Pipeline health DQ checks failed: {e}",
            )

            raise

    @task
    def update_watermarks(batch_info: dict) -> dict:
        """
        5. Update pipeline health watermark.
        """
        from src.metadata.watermark_manager import update_watermark
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed

        run_id = batch_info["run_id"]
        checked_at = batch_info["checked_at"]

        try:
            logger.info(
                f"Updating watermark 'pipeline_health' to checked_at={checked_at}"
            )

            update_watermark(
                source_name="pipeline_health",
                last_successful_value=checked_at,
            )

            return batch_info

        except Exception as e:
            logger.error(f"Error in update_watermarks task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Update pipeline health watermark failed: {e}",
            )

            raise

    @task
    def emit_pipeline_health_alerts(batch_info: dict) -> dict:
        """
        6. Emit alerts for any monitored DAGs in FAILED or STALE status.
        Uses deduplication to avoid notification storms.
        """
        from src.alerts.notifier import notify_alert
        from src.alerts.alert_models import AlertPayload, AlertSeverity, AlertType
        from src.alerts.alert_writer import resolve_open_alerts
        from src.common.db import fetch_all

        run_id = batch_info["run_id"]
        try:
            # 1. Emit alerts for unhealthy pipelines (FAILED or STALE)
            unhealthy_rows = fetch_all(
                """
                SELECT monitored_dag_id, health_status, health_message, freshness_lag_minutes, freshness_threshold_minutes
                FROM etl_metadata.pipeline_health_summary
                WHERE health_run_id = :run_id
                  AND health_status IN ('FAILED', 'STALE')
                """,
                {"run_id": run_id},
            )

            for row in unhealthy_rows:
                dag_id = row["monitored_dag_id"]
                health_status = row["health_status"]
                health_message = row.get("health_message") or f"Pipeline {dag_id} is {health_status}"

                severity = AlertSeverity.ERROR if health_status == "FAILED" else AlertSeverity.WARNING
                alert_type = AlertType.PIPELINE_DAG_FAILED if health_status == "FAILED" else AlertType.PIPELINE_DAG_STALE

                title = f"Pipeline Health Alert: {dag_id} is {health_status}"
                message = f"Monitored pipeline '{dag_id}' status is {health_status}. {health_message}"

                payload = AlertPayload(
                    alert_type=alert_type,
                    severity=severity,
                    source="pipeline_health",
                    title=title,
                    message=message,
                    dag_id=dag_id,
                    run_id=run_id,
                    details={
                        "health_status": health_status,
                        "health_message": health_message,
                        "freshness_lag_minutes": row.get("freshness_lag_minutes"),
                        "freshness_threshold_minutes": row.get("freshness_threshold_minutes"),
                    },
                )
                notify_alert(payload, check_dedup=True)

            # 2. Auto-resolve previous STALE / FAILED alerts for monitored DAGs that are now HEALTHY
            healthy_rows = fetch_all(
                """
                SELECT monitored_dag_id
                FROM etl_metadata.pipeline_health_summary
                WHERE health_run_id = :run_id
                  AND health_status = 'HEALTHY'
                """,
                {"run_id": run_id},
            )
            for h_row in healthy_rows:
                h_dag_id = h_row["monitored_dag_id"]
                resolve_open_alerts(dag_id=h_dag_id, alert_type=AlertType.PIPELINE_DAG_STALE)
                resolve_open_alerts(dag_id=h_dag_id, alert_type=AlertType.PIPELINE_DAG_FAILED)
                resolve_open_alerts(dag_id=h_dag_id, alert_type=AlertType.AIRFLOW_TASK_FAILURE)
                resolve_open_alerts(dag_id=h_dag_id, alert_type=AlertType.DATA_FRESHNESS_STALE)

        except Exception as e:
            logger.warning(f"Error checking and emitting pipeline health alerts (non-blocking): {e}")

        return batch_info

    @task
    def finish_pipeline(batch_info: dict) -> None:
        """
        7. Record pipeline completion success.
        """
        from src.common.db import fetch_one
        from src.monitoring.pipeline_health_builder import get_monitored_pipelines
        from src.metadata.pipeline_run_tracker import (
            finish_pipeline_run_success,
            finish_pipeline_run_failed,
        )

        run_id = batch_info["run_id"]

        records_extracted = len(get_monitored_pipelines())
        records_loaded = int(batch_info.get("health_rows_loaded", 0) or 0)

        try:
            rejected_row = fetch_one(
                """
                SELECT COUNT(*) AS rejected_count
                FROM etl_metadata.rejected_records
                WHERE run_id = :run_id
                """,
                {"run_id": run_id},
            )

            records_rejected = (
                int(rejected_row["rejected_count"] or 0)
                if rejected_row
                else 0
            )

            finish_pipeline_run_success(
                run_id=run_id,
                records_extracted=records_extracted,
                records_loaded=records_loaded,
                records_rejected=records_rejected,
            )

            logger.info(
                f"Pipeline health DAG completed successfully. "
                f"run_id={run_id}, "
                f"records_extracted={records_extracted}, "
                f"records_loaded={records_loaded}, "
                f"records_rejected={records_rejected}"
            )

        except Exception as e:
            logger.error(f"Error in finish_pipeline task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Finish pipeline health tracking failed: {e}",
            )

            raise

    batch_info_flow = start_pipeline()
    batch_info_flow = prepare_health_summary_for_rerun(batch_info_flow)
    batch_info_flow = build_health_summary(batch_info_flow)
    batch_info_flow = run_dq(batch_info_flow)
    batch_info_flow = update_watermarks(batch_info_flow)
    batch_info_flow = emit_pipeline_health_alerts(batch_info_flow)
    finish_pipeline(batch_info_flow)


dag_instance = pipeline_health_dag()