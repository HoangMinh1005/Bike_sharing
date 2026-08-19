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


def _parse_bool(value, field_name: str = "dry_run") -> bool:
    """
    Safely parse boolean config values from dag_run.conf.

    Accepted true values:
    - true
    - "true"
    - "1"
    - "yes"
    - "y"

    Accepted false values:
    - false
    - "false"
    - "0"
    - "no"
    - "n"

    This avoids Python behavior where bool("false") is True.
    """
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        value_clean = value.strip().lower()

        if value_clean in ("true", "1", "yes", "y"):
            return True

        if value_clean in ("false", "0", "no", "n"):
            return False

    raise ValueError(
        f"Invalid boolean value for '{field_name}': {value}. "
        "Use true or false."
    )


@dag(
    dag_id="retention_cleanup_dag",
    default_args=default_args,
    description="Automated Data Retention Cleanup Pipeline for Raw, Staging, and Metadata Tables",
    schedule="30 3 * * *",
    start_date=pendulum.datetime(2026, 7, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    tags=["cleanup", "retention", "metadata", "operations"],
)
def retention_cleanup_dag():
    @task
    def start_pipeline() -> dict:
        """
        Initialize pipeline run tracking for retention cleanup.

        Optional manual config:
        {
          "dry_run": true
        }
        """
        from airflow.operators.python import get_current_context
        from src.metadata.pipeline_run_tracker import (
            finish_pipeline_run_failed,
            start_pipeline_run,
        )

        context = get_current_context()
        dag_id = context["dag"].dag_id
        run_id = context["run_id"]
        batch_id = run_id

        try:
            logger.info(
                f"Starting retention cleanup pipeline run. "
                f"dag_id={dag_id}, run_id={run_id}"
            )

            start_pipeline_run(
                run_id=run_id,
                dag_id=dag_id,
            )

            dag_run = context.get("dag_run")
            conf = dag_run.conf if dag_run and dag_run.conf else {}

            dry_run = _parse_bool(
                conf.get("dry_run", False),
                field_name="dry_run",
            )

            if dry_run:
                logger.info(
                    "Retention cleanup is running in DRY RUN mode. "
                    "No records will be deleted."
                )
            else:
                logger.info(
                    "Retention cleanup is running in DELETE mode. "
                    "Expired records may be deleted according to policies."
                )

            return {
                "run_id": run_id,
                "batch_id": batch_id,
                "dag_id": dag_id,
                "dry_run": dry_run,
            }

        except Exception as e:
            logger.error(f"Error in start_pipeline task: {e}")

            try:
                finish_pipeline_run_failed(
                    run_id=run_id,
                    error_message=f"Start retention cleanup pipeline failed: {e}",
                )
            except Exception as tracking_error:
                logger.error(
                    f"Could not mark retention cleanup pipeline as failed: "
                    f"{tracking_error}"
                )

            raise

    @task
    def run_cleanup(batch_info: dict) -> dict:
        """
        Run retention cleanup across configured policies.

        fail_on_any_error=False:
        - One table-level failure will be logged and included in summary.
        - Cleanup continues for other tables.
        - The manager still raises if all processed tables fail.
        """
        from src.cleanup.retention_manager import run_retention_cleanup
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed

        run_id = batch_info["run_id"]
        dry_run = batch_info["dry_run"]

        try:
            logger.info(
                f"Executing run_retention_cleanup. dry_run={dry_run}"
            )

            summary = run_retention_cleanup(
                dry_run=dry_run,
                enabled_only=True,
                allow_disabled=False,
                fail_on_any_error=False,
            )

            logger.info(f"Retention cleanup summary: {summary}")

            return {
                **batch_info,
                "summary": summary,
            }

        except Exception as e:
            logger.error(f"Error in run_cleanup task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Run retention cleanup failed: {e}",
            )

            raise

    @task
    def update_watermarks(batch_info: dict) -> dict:
        """
        Update retention_cleanup watermark.

        Note:
        For manual dry_run=True, this DAG still updates the watermark to record
        that the retention check ran successfully.
        """
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed
        from src.metadata.watermark_manager import update_watermark

        run_id = batch_info["run_id"]
        dry_run = batch_info["dry_run"]
        now_str = pendulum.now("UTC").to_iso8601_string()

        try:
            logger.info(
                f"Updating watermark. source_name=retention_cleanup, "
                f"last_successful_value={now_str}, dry_run={dry_run}"
            )

            update_watermark(
                source_name="retention_cleanup",
                last_successful_value=now_str,
            )

            return batch_info

        except Exception as e:
            logger.error(f"Error in update_watermarks task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Update retention cleanup watermark failed: {e}",
            )

            raise

    @task
    def finish_pipeline(batch_info: dict) -> None:
        """
        Mark retention cleanup pipeline run as successful.
        """
        from src.metadata.pipeline_run_tracker import (
            finish_pipeline_run_failed,
            finish_pipeline_run_success,
        )

        run_id = batch_info["run_id"]
        summary = batch_info.get("summary", {})

        tables_processed = int(
            summary.get("tables_processed", 0) or 0
        )
        total_rows_affected = int(
            summary.get("total_rows_affected", 0) or 0
        )
        failed_tables = int(
            summary.get("failed_tables", 0) or 0
        )
        dry_run = bool(
            summary.get("dry_run", batch_info.get("dry_run", False))
        )

        try:
            logger.info(
                f"Marking retention_cleanup_dag as success. "
                f"run_id={run_id}, "
                f"dry_run={dry_run}, "
                f"tables_processed={tables_processed}, "
                f"failed_tables={failed_tables}, "
                f"total_rows_affected={total_rows_affected}"
            )

            finish_pipeline_run_success(
                run_id=run_id,
                records_extracted=tables_processed,
                records_loaded=0,
                records_rejected=0,
            )

        except Exception as e:
            logger.error(f"Error in finish_pipeline task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Finish retention cleanup pipeline tracking failed: {e}",
            )

            raise

    batch_info = start_pipeline()
    batch_info = run_cleanup(batch_info)
    batch_info = update_watermarks(batch_info)
    finish_pipeline(batch_info)


dag_instance = retention_cleanup_dag()