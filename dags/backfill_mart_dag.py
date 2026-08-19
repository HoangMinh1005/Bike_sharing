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
    dag_id="backfill_mart_dag",
    default_args=default_args,
    on_failure_callback=airflow_task_failure_callback,
    description="Manual Backfill Pipeline for Hourly and Daily Mart Tables",
    schedule=None,
    start_date=pendulum.datetime(2026, 7, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    tags=["backfill", "mart", "etl", "operations"],
)
def backfill_mart_dag():
    @task
    def start_pipeline() -> dict:
        """
        Initialize pipeline run tracking for manual mart backfill.

        This DAG must be triggered manually with dag_run.conf.
        Required config:
        {
          "backfill_type": "hourly" | "daily" | "both",
          "start": "...",
          "end": "..."
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
                f"Starting manual backfill pipeline run. "
                f"dag_id={dag_id}, run_id={run_id}"
            )

            start_pipeline_run(
                run_id=run_id,
                dag_id=dag_id,
            )

            dag_run = context.get("dag_run")
            conf = dag_run.conf if dag_run and dag_run.conf else {}

            if not conf:
                raise ValueError(
                    "backfill_mart_dag requires dag_run.conf. "
                    "Please provide: backfill_type, start, and end."
                )

            logger.info(f"Received backfill config: {conf}")

            return {
                "run_id": run_id,
                "batch_id": batch_id,
                "dag_id": dag_id,
                "conf": conf,
            }

        except Exception as e:
            logger.error(f"Error in start_pipeline task: {e}")

            try:
                finish_pipeline_run_failed(
                    run_id=run_id,
                    error_message=f"Start backfill pipeline failed: {e}",
                )
            except Exception as tracking_error:
                logger.error(
                    f"Could not mark backfill pipeline as failed: {tracking_error}"
                )

            raise

    @task
    def parse_and_validate_backfill_conf(batch_info: dict) -> dict:
        """
        Parse and validate backfill configuration.

        Important:
        Use normalized start/end returned by parse_backfill_conf(),
        not raw conf values, because the manager may floor/ceil hourly windows.
        """
        from src.backfill.backfill_manager import parse_backfill_conf
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed

        run_id = batch_info["run_id"]
        conf = batch_info["conf"]

        try:
            parsed = parse_backfill_conf(conf)

            logger.info(
                f"Validated backfill configuration. "
                f"backfill_type={parsed['backfill_type']}, "
                f"start={parsed['start']}, "
                f"end={parsed['end']}, "
                f"start_date={parsed['start_date']}, "
                f"end_date={parsed['end_date']}"
            )

            return {
                **batch_info,
                "backfill_type": parsed["backfill_type"],
                "start": parsed["start"],
                "end": parsed["end"],
                "start_date": parsed["start_date"],
                "end_date": parsed["end_date"],
                "business_timezone": parsed.get("business_timezone", "UTC"),
            }

        except Exception as e:
            logger.error(f"Error in parse_and_validate_backfill_conf task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Validate backfill config failed: {e}",
            )

            raise

    @task
    def run_backfill(batch_info: dict) -> dict:
        """
        Execute mart backfill over the requested range.
        """
        from src.backfill.backfill_manager import backfill_mart_range
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed

        run_id = batch_info["run_id"]
        batch_id = batch_info["batch_id"]
        backfill_type = batch_info["backfill_type"]
        start = batch_info["start"]
        end = batch_info["end"]
        business_timezone = batch_info.get("business_timezone", "UTC")

        try:
            logger.info(
                f"Executing mart backfill. "
                f"backfill_type={backfill_type}, "
                f"start={start}, end={end}, "
                f"batch_id={batch_id}, run_id={run_id}"
            )

            summary = backfill_mart_range(
                backfill_type=backfill_type,
                start=start,
                end=end,
                batch_id=batch_id,
                run_id=run_id,
                business_timezone=business_timezone,
                weather_enabled=True,
                weather_required=True,
                vehicle_type_required=False,
                include_partition_details=False,
            )

            logger.info(f"Backfill completed with summary: {summary}")

            return {
                **batch_info,
                "summary": summary,
            }

        except Exception as e:
            logger.error(f"Error in run_backfill task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Run mart backfill failed: {e}",
            )

            raise

    @task
    def update_watermarks(batch_info: dict) -> dict:
        """
        Update backfill_mart watermark after successful backfill.
        """
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed
        from src.metadata.watermark_manager import update_watermark

        run_id = batch_info["run_id"]
        end_value = batch_info["end"]

        try:
            logger.info(
                f"Updating watermark. source_name=backfill_mart, "
                f"last_successful_value={end_value}"
            )

            update_watermark(
                source_name="backfill_mart",
                last_successful_value=end_value,
            )

            return batch_info

        except Exception as e:
            logger.error(f"Error in update_watermarks task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Update backfill watermark failed: {e}",
            )

            raise

    @task
    def finish_pipeline(batch_info: dict) -> None:
        """
        Mark backfill pipeline run as successful.
        """
        from src.common.db import fetch_one
        from src.metadata.pipeline_run_tracker import (
            finish_pipeline_run_failed,
            finish_pipeline_run_success,
        )

        run_id = batch_info["run_id"]
        summary = batch_info.get("summary", {})

        records_extracted = int(
            summary.get("total_windows_or_dates_processed", 0) or 0
        )
        records_loaded = int(
            summary.get("total_records_loaded", 0) or 0
        )

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

            logger.info(
                f"Marking backfill_mart_dag as success. "
                f"run_id={run_id}, "
                f"records_extracted={records_extracted}, "
                f"records_loaded={records_loaded}, "
                f"records_rejected={records_rejected}"
            )

            finish_pipeline_run_success(
                run_id=run_id,
                records_extracted=records_extracted,
                records_loaded=records_loaded,
                records_rejected=records_rejected,
            )

        except Exception as e:
            logger.error(f"Error in finish_pipeline task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Finish backfill pipeline tracking failed: {e}",
            )

            raise

    batch_info = start_pipeline()
    batch_info = parse_and_validate_backfill_conf(batch_info)
    batch_info = run_backfill(batch_info)
    batch_info = update_watermarks(batch_info)
    finish_pipeline(batch_info)


dag_instance = backfill_mart_dag()