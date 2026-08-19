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

    # For this MVP DAG, retries are disabled because each task manually
    # marks the pipeline run as failed when an exception occurs.
    #
    # If retries > 0, a task can mark the pipeline as failed on the first
    # attempt, then succeed on retry, causing confusing pipeline status history.
    "retries": 0,
    "on_failure_callback": airflow_task_failure_callback,
    "on_success_callback": airflow_task_success_callback,
}


@dag(
    dag_id="daily_summary_dag",
    default_args=default_args,
    on_failure_callback=airflow_task_failure_callback,
    description="Daily Summary and Station Demand Ranking Mart Pipeline",
    schedule="30 1 * * *",
    start_date=pendulum.datetime(2026, 7, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    tags=["mart", "daily", "summary", "ranking", "etl"],
)
def daily_summary_dag():
    @task
    def start_pipeline() -> dict:
        """
        1. Initialize pipeline run tracking.
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

        try:
            logger.info(
                f"Starting pipeline run '{run_id}' for DAG '{dag_id}'"
            )

            start_pipeline_run(
                run_id=run_id,
                dag_id=dag_id,
            )

            return {
                "run_id": run_id,
                "batch_id": batch_id,
                "dag_id": dag_id,
            }

        except Exception as e:
            logger.error(f"Error in start_pipeline task: {e}")

            try:
                finish_pipeline_run_failed(
                    run_id=run_id,
                    error_message=(
                        f"Start daily summary pipeline tracking failed: {e}"
                    ),
                )
            except Exception as tracking_error:
                logger.error(
                    f"Could not mark pipeline as failed after start error: "
                    f"{tracking_error}"
                )

            raise

    @task
    def determine_target_date(batch_info: dict) -> dict:
        """
        2. Determine target_date for daily summary building.

        Priority:
        1. Use dag_run.conf if target_date is provided.
        2. Otherwise, use Airflow data_interval_end minus 1 day.

        Example:
            If DAG runs on 2026-07-22 01:30:00,
            target_date = 2026-07-21.
        """
        from airflow.operators.python import get_current_context
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed

        context = get_current_context()
        run_id = batch_info["run_id"]

        try:
            dag_run = context.get("dag_run")
            conf = dag_run.conf if dag_run and dag_run.conf else {}

            conf_target_date = conf.get("target_date")

            if conf_target_date:
                try:
                    target_dt = pendulum.parse(str(conf_target_date))
                    target_date = target_dt.to_date_string()
                except Exception as e:
                    raise ValueError(
                        f"Invalid target_date format from dag_run.conf. "
                        f"target_date={conf_target_date}, error={e}"
                    ) from e

                logger.info(
                    f"Using target_date from dag_run.conf: {target_date}"
                )

            else:
                data_interval_end = context.get("data_interval_end")

                if data_interval_end:
                    base_dt = pendulum.instance(
                        data_interval_end
                    ).in_timezone("UTC")
                else:
                    # This fallback is only for unusual manual/test contexts
                    # where Airflow does not provide data_interval_end.
                    base_dt = pendulum.now("UTC")

                target_dt = base_dt.subtract(days=1)
                target_date = target_dt.to_date_string()

                logger.info(
                    f"Calculated default target_date from Airflow data interval: "
                    f"{target_date}"
                )

            return {
                **batch_info,
                "target_date": target_date,
            }

        except Exception as e:
            logger.error(f"Error in determine_target_date task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Determine target_date failed: {e}",
            )

            raise

    @task
    def prepare_daily_mart_for_rerun(batch_info: dict) -> dict:
        """
        3. Delete existing records in daily mart tables for target_date.

        This makes reruns idempotent.
        Only daily mart tables are deleted. Hourly mart source tables are not touched.
        """
        from src.common.db import execute_sql
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed

        run_id = batch_info["run_id"]
        target_date = batch_info["target_date"]

        try:
            logger.info(
                f"Preparing daily mart for rerun on target_date={target_date}"
            )

            params = {
                "target_date": target_date,
            }

            deleted_system = execute_sql(
                """
                DELETE FROM mart.daily_system_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                """,
                params,
            )

            deleted_ranking = execute_sql(
                """
                DELETE FROM mart.station_demand_ranking
                WHERE ranking_date = CAST(:target_date AS DATE)
                """,
                params,
            )

            deleted_region = execute_sql(
                """
                DELETE FROM mart.daily_region_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                """,
                params,
            )

            deleted_station = execute_sql(
                """
                DELETE FROM mart.daily_station_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                """,
                params,
            )

            logger.info(
                f"Deleted existing daily mart records for target_date={target_date}: "
                f"system_summary={deleted_system}, "
                f"demand_ranking={deleted_ranking}, "
                f"region_summary={deleted_region}, "
                f"station_summary={deleted_station}"
            )

            return batch_info

        except Exception as e:
            logger.error(f"Error in prepare_daily_mart_for_rerun task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Prepare daily mart for rerun failed: {e}",
            )

            raise

    @task
    def build_daily_station_summary_task(batch_info: dict) -> dict:
        """
        4. Build mart.daily_station_summary.
        """
        from src.mart.daily_mart_builder import build_daily_station_summary
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed

        run_id = batch_info["run_id"]
        batch_id = batch_info["batch_id"]
        target_date = batch_info["target_date"]

        try:
            loaded = build_daily_station_summary(
                target_date=target_date,
                batch_id=batch_id,
                run_id=run_id,
            )

            if loaded <= 0:
                raise RuntimeError(
                    f"No records built for mart.daily_station_summary "
                    f"on target_date={target_date}. "
                    f"Check mart.hourly_station_availability source data."
                )

            logger.info(
                f"Built daily station summary mart: {loaded} rows."
            )

            return {
                **batch_info,
                "daily_station_mart_loaded": loaded,
            }

        except Exception as e:
            logger.error(f"Error in build_daily_station_summary_task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Build daily station summary mart failed: {e}",
            )

            raise

    @task
    def build_daily_region_summary_task(batch_info: dict) -> dict:
        """
        5. Build mart.daily_region_summary.
        """
        from src.mart.daily_mart_builder import build_daily_region_summary
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed

        run_id = batch_info["run_id"]
        batch_id = batch_info["batch_id"]
        target_date = batch_info["target_date"]

        try:
            loaded = build_daily_region_summary(
                target_date=target_date,
                batch_id=batch_id,
                run_id=run_id,
            )

            if loaded <= 0:
                raise RuntimeError(
                    f"No records built for mart.daily_region_summary "
                    f"on target_date={target_date}."
                )

            logger.info(
                f"Built daily region summary mart: {loaded} rows."
            )

            return {
                **batch_info,
                "daily_region_mart_loaded": loaded,
            }

        except Exception as e:
            logger.error(f"Error in build_daily_region_summary_task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Build daily region summary mart failed: {e}",
            )

            raise

    @task
    def build_station_demand_ranking_task(batch_info: dict) -> dict:
        """
        6. Build mart.station_demand_ranking.
        """
        from src.mart.daily_mart_builder import build_station_demand_ranking
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed

        run_id = batch_info["run_id"]
        batch_id = batch_info["batch_id"]
        target_date = batch_info["target_date"]

        try:
            loaded = build_station_demand_ranking(
                target_date=target_date,
                batch_id=batch_id,
                run_id=run_id,
            )

            if loaded <= 0:
                raise RuntimeError(
                    f"No records built for mart.station_demand_ranking "
                    f"on target_date={target_date}."
                )

            logger.info(
                f"Built station demand ranking mart: {loaded} rows."
            )

            return {
                **batch_info,
                "demand_ranking_mart_loaded": loaded,
            }

        except Exception as e:
            logger.error(f"Error in build_station_demand_ranking_task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Build station demand ranking mart failed: {e}",
            )

            raise

    @task
    def build_daily_system_summary_task(batch_info: dict) -> dict:
        """
        7. Build mart.daily_system_summary.
        """
        from src.mart.daily_mart_builder import build_daily_system_summary
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed

        run_id = batch_info["run_id"]
        batch_id = batch_info["batch_id"]
        target_date = batch_info["target_date"]

        try:
            loaded = build_daily_system_summary(
                target_date=target_date,
                batch_id=batch_id,
                run_id=run_id,
            )

            if loaded <= 0:
                raise RuntimeError(
                    f"No records built for mart.daily_system_summary "
                    f"on target_date={target_date}."
                )

            logger.info(
                f"Built daily system summary mart: {loaded} rows."
            )

            return {
                **batch_info,
                "daily_system_mart_loaded": loaded,
            }

        except Exception as e:
            logger.error(f"Error in build_daily_system_summary_task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Build daily system summary mart failed: {e}",
            )

            raise

    @task
    def run_dq(batch_info: dict) -> dict:
        """
        8. Run data quality checks for daily mart tables.
        """
        from src.quality.daily_mart_checks import run_daily_mart_dq_checks
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed

        run_id = batch_info["run_id"]
        batch_id = batch_info["batch_id"]
        target_date = batch_info["target_date"]

        try:
            logger.info(
                f"Running daily mart DQ checks for target_date={target_date}"
            )

            run_daily_mart_dq_checks(
                run_id=run_id,
                batch_id=batch_id,
                target_date=target_date,
            )

            return batch_info

        except Exception as e:
            logger.error(f"Error in run_dq task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Daily mart DQ checks failed: {e}",
            )

            raise

    @task
    def update_watermarks(batch_info: dict) -> dict:
        """
        9. Update daily summary watermark.
        """
        from src.metadata.watermark_manager import update_watermark
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed

        run_id = batch_info["run_id"]
        target_date = batch_info["target_date"]

        try:
            logger.info(
                f"Updating watermark 'daily_summary' to target_date={target_date}"
            )

            update_watermark(
                source_name="daily_summary",
                last_successful_value=target_date,
            )

            return batch_info

        except Exception as e:
            logger.error(f"Error in update_watermarks task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Update daily summary watermark failed: {e}",
            )

            raise

    @task
    def finish_pipeline(batch_info: dict) -> None:
        """
        10. Record pipeline completion success.
        """
        from src.common.db import fetch_one
        from src.metadata.pipeline_run_tracker import (
            finish_pipeline_run_success,
            finish_pipeline_run_failed,
        )

        run_id = batch_info["run_id"]

        station_mart = int(batch_info.get("daily_station_mart_loaded", 0) or 0)
        region_mart = int(batch_info.get("daily_region_mart_loaded", 0) or 0)
        ranking_mart = int(batch_info.get("demand_ranking_mart_loaded", 0) or 0)
        system_mart = int(batch_info.get("daily_system_mart_loaded", 0) or 0)

        total_records_loaded = (
            station_mart
            + region_mart
            + ranking_mart
            + system_mart
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
                f"Marking daily_summary_dag pipeline run as success. "
                f"run_id={run_id}, "
                f"daily_station_mart={station_mart}, "
                f"daily_region_mart={region_mart}, "
                f"demand_ranking_mart={ranking_mart}, "
                f"daily_system_mart={system_mart}, "
                f"total_records_loaded={total_records_loaded}, "
                f"records_rejected={records_rejected}"
            )

            finish_pipeline_run_success(
                run_id=run_id,
                records_extracted=4,
                records_loaded=total_records_loaded,
                records_rejected=records_rejected,
            )

            logger.info(
                f"Daily summary build pipeline completed successfully. "
                f"run_id={run_id}"
            )

        except Exception as e:
            logger.error(f"Error in finish_pipeline task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=(
                    f"Finish daily summary pipeline tracking failed: {e}"
                ),
            )

            raise

    batch_info_flow = start_pipeline()
    batch_info_flow = determine_target_date(batch_info_flow)
    batch_info_flow = prepare_daily_mart_for_rerun(batch_info_flow)
    batch_info_flow = build_daily_station_summary_task(batch_info_flow)
    batch_info_flow = build_daily_region_summary_task(batch_info_flow)
    batch_info_flow = build_station_demand_ranking_task(batch_info_flow)
    batch_info_flow = build_daily_system_summary_task(batch_info_flow)
    batch_info_flow = run_dq(batch_info_flow)
    batch_info_flow = update_watermarks(batch_info_flow)
    finish_pipeline(batch_info_flow)


dag_instance = daily_summary_dag()