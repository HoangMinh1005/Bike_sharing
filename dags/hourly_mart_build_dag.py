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
    dag_id="hourly_mart_build_dag",
    default_args=default_args,
    on_failure_callback=airflow_task_failure_callback,
    description="ETL pipeline for building hourly analytical mart tables",
    schedule="20 * * * *",
    start_date=pendulum.datetime(2026, 7, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    tags=["mart", "hourly", "analytics", "etl"],
)
def hourly_mart_build_dag():
    @task
    def start_pipeline() -> dict:
        """
        1. Initialize pipeline run tracking.
        """
        from airflow.operators.python import get_current_context
        from src.metadata.pipeline_run_tracker import start_pipeline_run

        context = get_current_context()

        dag_id = context["dag"].dag_id
        run_id = context["run_id"]
        batch_id = run_id

        logger.info(
            f"Starting hourly mart build pipeline. "
            f"dag_id={dag_id}, run_id={run_id}, batch_id={batch_id}"
        )

        start_pipeline_run(
            run_id=run_id,
            dag_id=dag_id,
        )

        return {
            "run_id": run_id,
            "batch_id": batch_id,
        }

    @task
    def determine_target_window(batch_info: dict) -> dict:
        """
        2. Determine target_hour_start and target_hour_end.

        Priority:
        1. Use dag_run.conf if both target_hour_start and target_hour_end are provided.
        2. Otherwise, use Airflow data_interval_end to build the previous complete hour.

        Example:
        If DAG runs at 10:20, target window should be:
        09:00:00 -> 10:00:00
        """
        from airflow.operators.python import get_current_context

        context = get_current_context()

        dag_run = context.get("dag_run")
        conf = dag_run.conf if dag_run and dag_run.conf else {}

        conf_start = conf.get("target_hour_start")
        conf_end = conf.get("target_hour_end")

        if bool(conf_start) != bool(conf_end):
            raise ValueError(
                "Both target_hour_start and target_hour_end must be provided "
                "together when using dag_run.conf."
            )

        if conf_start and conf_end:
            try:
                start_dt = pendulum.parse(str(conf_start)).in_timezone("UTC")
                end_dt = pendulum.parse(str(conf_end)).in_timezone("UTC")
            except Exception as e:
                raise ValueError(
                    f"Invalid target window format from dag_run.conf. "
                    f"target_hour_start={conf_start}, "
                    f"target_hour_end={conf_end}, error={e}"
                ) from e

            if start_dt >= end_dt:
                raise ValueError(
                    f"Invalid target window: target_hour_start={conf_start} "
                    f"must be earlier than target_hour_end={conf_end}"
                )

            target_hour_start = start_dt.to_datetime_string()
            target_hour_end = end_dt.to_datetime_string()

            logger.info(
                f"Using target window from dag_run.conf: "
                f"start={target_hour_start}, end={target_hour_end}"
            )

        else:
            data_interval_end = context.get("data_interval_end")

            if data_interval_end:
                base_dt = pendulum.instance(data_interval_end).in_timezone("UTC")
            else:
                # Fallback for unusual manual execution contexts.
                base_dt = pendulum.now("UTC")

            target_end_dt = base_dt.replace(
                minute=0,
                second=0,
                microsecond=0,
            )
            target_start_dt = target_end_dt.subtract(hours=1)

            target_hour_start = target_start_dt.to_datetime_string()
            target_hour_end = target_end_dt.to_datetime_string()

            logger.info(
                f"Calculated default hourly target window from Airflow data interval: "
                f"start={target_hour_start}, end={target_hour_end}"
            )

        return {
            **batch_info,
            "target_hour_start": target_hour_start,
            "target_hour_end": target_hour_end,
        }

    @task
    def prepare_mart_for_rerun(batch_info: dict) -> dict:
        """
        3. Clean existing mart records within target window before rebuilding.
        """
        from src.common.db import execute_sql
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed

        run_id = batch_info["run_id"]
        target_hour_start = batch_info["target_hour_start"]
        target_hour_end = batch_info["target_hour_end"]

        try:
            logger.info(
                f"Cleaning existing mart records in target window "
                f"[{target_hour_start} to {target_hour_end}]"
            )

            params = {
                "target_hour_start": target_hour_start,
                "target_hour_end": target_hour_end,
            }

            deleted_weather_mobility = execute_sql(
                """
                DELETE FROM mart.weather_mobility_summary
                WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
                  AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
                """,
                params,
            )

            deleted_vehicle_type = execute_sql(
                """
                DELETE FROM mart.vehicle_type_availability_summary
                WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
                  AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
                """,
                params,
            )

            deleted_region = execute_sql(
                """
                DELETE FROM mart.hourly_region_availability
                WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
                  AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
                """,
                params,
            )

            deleted_station = execute_sql(
                """
                DELETE FROM mart.hourly_station_availability
                WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
                  AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
                """,
                params,
            )

            logger.info(
                f"Deleted existing mart records: "
                f"weather_mobility={deleted_weather_mobility}, "
                f"vehicle_type={deleted_vehicle_type}, "
                f"region_availability={deleted_region}, "
                f"station_availability={deleted_station}"
            )

            return batch_info

        except Exception as e:
            logger.error(f"Error in prepare_mart_for_rerun task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Prepare mart for rerun failed: {e}",
            )

            raise

    @task
    def build_station_hourly_mart(batch_info: dict) -> dict:
        """
        4. Build mart.hourly_station_availability.
        """
        from src.mart.hourly_mart_builder import build_hourly_station_availability
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed

        run_id = batch_info["run_id"]
        batch_id = batch_info["batch_id"]
        target_hour_start = batch_info["target_hour_start"]
        target_hour_end = batch_info["target_hour_end"]

        try:
            station_mart_loaded = build_hourly_station_availability(
                target_hour_start=target_hour_start,
                target_hour_end=target_hour_end,
                batch_id=batch_id,
                run_id=run_id,
            )

            if station_mart_loaded <= 0:
                raise RuntimeError(
                    f"No station hourly availability records built for window "
                    f"[{target_hour_start} to {target_hour_end}]."
                )

            logger.info(
                f"Built station hourly availability mart: "
                f"{station_mart_loaded} rows."
            )

            return {
                **batch_info,
                "station_mart_loaded": station_mart_loaded,
            }

        except Exception as e:
            logger.error(f"Error in build_station_hourly_mart task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Build station hourly availability mart failed: {e}",
            )

            raise

    @task
    def build_region_hourly_mart(batch_info: dict) -> dict:
        """
        5. Build mart.hourly_region_availability.
        """
        from src.mart.hourly_mart_builder import build_hourly_region_availability
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed

        run_id = batch_info["run_id"]
        batch_id = batch_info["batch_id"]
        target_hour_start = batch_info["target_hour_start"]
        target_hour_end = batch_info["target_hour_end"]

        try:
            region_mart_loaded = build_hourly_region_availability(
                target_hour_start=target_hour_start,
                target_hour_end=target_hour_end,
                batch_id=batch_id,
                run_id=run_id,
            )

            if region_mart_loaded <= 0:
                raise RuntimeError(
                    f"No region hourly availability records built for window "
                    f"[{target_hour_start} to {target_hour_end}]."
                )

            logger.info(
                f"Built region hourly availability mart: "
                f"{region_mart_loaded} rows."
            )

            return {
                **batch_info,
                "region_mart_loaded": region_mart_loaded,
            }

        except Exception as e:
            logger.error(f"Error in build_region_hourly_mart task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Build region hourly availability mart failed: {e}",
            )

            raise

    @task
    def build_vehicle_type_hourly_mart(batch_info: dict) -> dict:
        """
        6. Build mart.vehicle_type_availability_summary.
        """
        from src.mart.hourly_mart_builder import (
            build_vehicle_type_availability_summary,
        )
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed

        run_id = batch_info["run_id"]
        batch_id = batch_info["batch_id"]
        target_hour_start = batch_info["target_hour_start"]
        target_hour_end = batch_info["target_hour_end"]

        try:
            vehicle_type_mart_loaded = build_vehicle_type_availability_summary(
                target_hour_start=target_hour_start,
                target_hour_end=target_hour_end,
                batch_id=batch_id,
                run_id=run_id,
            )

            if vehicle_type_mart_loaded <= 0:
                logger.warning(
                    f"No vehicle type availability summary records built for window "
                    f"[{target_hour_start} to {target_hour_end}]."
                )
            else:
                logger.info(
                    f"Built vehicle type availability summary mart: "
                    f"{vehicle_type_mart_loaded} rows."
                )

            return {
                **batch_info,
                "vehicle_type_mart_loaded": vehicle_type_mart_loaded,
            }

        except Exception as e:
            logger.error(f"Error in build_vehicle_type_hourly_mart task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Build vehicle type availability summary failed: {e}",
            )

            raise

    @task
    def build_weather_mobility_hourly_mart(batch_info: dict) -> dict:
        """
        7. Build mart.weather_mobility_summary.
        """
        from src.mart.hourly_mart_builder import build_weather_mobility_summary
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed

        run_id = batch_info["run_id"]
        batch_id = batch_info["batch_id"]
        target_hour_start = batch_info["target_hour_start"]
        target_hour_end = batch_info["target_hour_end"]

        try:
            weather_mobility_mart_loaded = build_weather_mobility_summary(
                target_hour_start=target_hour_start,
                target_hour_end=target_hour_end,
                batch_id=batch_id,
                run_id=run_id,
            )

            if weather_mobility_mart_loaded <= 0:
                raise RuntimeError(
                    f"No weather mobility summary records built for window "
                    f"[{target_hour_start} to {target_hour_end}]."
                )

            logger.info(
                f"Built weather mobility summary mart: "
                f"{weather_mobility_mart_loaded} rows."
            )

            return {
                **batch_info,
                "weather_mobility_mart_loaded": weather_mobility_mart_loaded,
            }

        except Exception as e:
            logger.error(f"Error in build_weather_mobility_hourly_mart task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Build weather mobility summary failed: {e}",
            )

            raise

    @task
    def run_dq(batch_info: dict) -> dict:
        """
        8. Execute hourly mart Data Quality checks.
        """
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed
        from src.quality.hourly_mart_checks import run_hourly_mart_dq_checks

        run_id = batch_info["run_id"]
        batch_id = batch_info["batch_id"]
        target_hour_start = batch_info["target_hour_start"]
        target_hour_end = batch_info["target_hour_end"]

        try:
            logger.info(
                f"Running hourly mart DQ checks for window "
                f"[{target_hour_start} to {target_hour_end}]"
            )

            run_hourly_mart_dq_checks(
                run_id=run_id,
                batch_id=batch_id,
                target_hour_start=target_hour_start,
                target_hour_end=target_hour_end,
            )

            logger.info("Hourly mart DQ checks passed successfully.")

            return batch_info

        except Exception as e:
            logger.error(f"Error in run_dq task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Hourly mart DQ checks failed: {e}",
            )

            raise

    @task
    def update_watermarks(batch_info: dict) -> dict:
        """
        9. Update watermark for hourly_mart.
        """
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed
        from src.metadata.watermark_manager import update_watermark

        run_id = batch_info["run_id"]
        target_hour_end = batch_info["target_hour_end"]

        try:
            logger.info(f"Updating hourly_mart watermark to: {target_hour_end}")

            update_watermark(
                source_name="hourly_mart",
                last_successful_value=target_hour_end,
            )

            return {
                **batch_info,
                "hourly_mart_watermark": target_hour_end,
            }

        except Exception as e:
            logger.error(f"Error in update_watermarks task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Hourly mart watermark update failed: {e}",
            )

            raise

    @task
    def finish_pipeline(batch_info: dict) -> None:
        """
        10. Complete pipeline tracking.
        """
        from src.common.db import fetch_one
        from src.metadata.pipeline_run_tracker import (
            finish_pipeline_run_failed,
            finish_pipeline_run_success,
        )

        run_id = batch_info["run_id"]

        station_mart = batch_info.get("station_mart_loaded", 0)
        region_mart = batch_info.get("region_mart_loaded", 0)
        vehicle_type_mart = batch_info.get("vehicle_type_mart_loaded", 0)
        weather_mart = batch_info.get("weather_mobility_mart_loaded", 0)

        total_records_loaded = (
            station_mart
            + region_mart
            + vehicle_type_mart
            + weather_mart
        )

        try:
            rejected_row = fetch_one(
                """
                SELECT COUNT(*) AS rejected_count
                FROM etl_metadata.rejected_records
                WHERE run_id = :run_id
                """,
                {
                    "run_id": run_id,
                },
            )

            records_rejected = (
                int(rejected_row["rejected_count"])
                if rejected_row and rejected_row["rejected_count"] is not None
                else 0
            )

            logger.info(
                f"Marking hourly_mart_build_dag pipeline run as success. "
                f"run_id={run_id}, "
                f"station_mart={station_mart}, "
                f"region_mart={region_mart}, "
                f"vehicle_type_mart={vehicle_type_mart}, "
                f"weather_mart={weather_mart}, "
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
                f"Hourly mart build pipeline completed successfully. "
                f"run_id={run_id}"
            )

        except Exception as e:
            logger.error(f"Error in finish_pipeline task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Finish hourly mart pipeline tracking failed: {e}",
            )

            raise

    batch_info_flow = start_pipeline()
    batch_info_flow = determine_target_window(batch_info_flow)
    batch_info_flow = prepare_mart_for_rerun(batch_info_flow)
    batch_info_flow = build_station_hourly_mart(batch_info_flow)
    batch_info_flow = build_region_hourly_mart(batch_info_flow)
    batch_info_flow = build_vehicle_type_hourly_mart(batch_info_flow)
    batch_info_flow = build_weather_mobility_hourly_mart(batch_info_flow)
    batch_info_flow = run_dq(batch_info_flow)
    batch_info_flow = update_watermarks(batch_info_flow)
    finish_pipeline(batch_info_flow)


dag_instance = hourly_mart_build_dag()