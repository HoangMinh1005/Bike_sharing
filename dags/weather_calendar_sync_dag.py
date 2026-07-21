import pendulum
from airflow.decorators import dag, task
from src.common.logger import get_logger

logger = get_logger(__name__)

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 0,
}


@dag(
    dag_id="weather_calendar_sync_dag",
    default_args=default_args,
    description="ETL pipeline for weather and calendar enrichment every 3 hours",
    schedule="0 */3 * * *",
    start_date=pendulum.datetime(2026, 7, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    tags=["weather", "calendar", "enrichment", "etl"],
)
def weather_calendar_sync_dag():

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
            f"Starting weather_calendar pipeline run. "
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
    def prepare_batch_for_rerun(batch_info: dict) -> dict:
        """
        2. Clean raw and staging records for this batch_id before rerun.
        """
        from src.common.db import execute_sql
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed

        run_id = batch_info["run_id"]
        batch_id = batch_info["batch_id"]

        try:
            logger.info(
                f"Cleaning existing weather/calendar records for batch_id={batch_id}"
            )

            del_stg_weather = execute_sql(
                "DELETE FROM staging.weather_hourly WHERE batch_id = :batch_id",
                {"batch_id": batch_id},
            )
            del_stg_cal = execute_sql(
                "DELETE FROM staging.calendar WHERE batch_id = :batch_id",
                {"batch_id": batch_id},
            )
            del_raw_weather = execute_sql(
                "DELETE FROM raw.weather_hourly WHERE batch_id = :batch_id",
                {"batch_id": batch_id},
            )
            del_raw_cal = execute_sql(
                "DELETE FROM raw.calendar WHERE batch_id = :batch_id",
                {"batch_id": batch_id},
            )

            logger.info(
                f"Deleted existing records: "
                f"staging.weather={del_stg_weather}, staging.calendar={del_stg_cal}, "
                f"raw.weather={del_raw_weather}, raw.calendar={del_raw_cal}"
            )

            return batch_info

        except Exception as e:
            logger.error(f"Error in prepare_batch_for_rerun task: {e}")
            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Prepare batch for rerun failed: {e}",
            )
            raise

    @task
    def extract_and_load_weather(batch_info: dict) -> dict:
        """
        3. Fetch hourly weather parameters and load raw snapshots.
        """
        from src.common.config import get_settings
        from src.extract.weather_client import WeatherClient
        from src.load.weather_raw_loader import load_weather_raw
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed

        settings = get_settings()
        run_id = batch_info["run_id"]
        batch_id = batch_info["batch_id"]

        try:
            client = WeatherClient(settings.WEATHER_API_BASE_URL)
            payload = client.fetch_hourly_weather(
                latitude=settings.WEATHER_LATITUDE,
                longitude=settings.WEATHER_LONGITUDE,
                timezone=settings.WEATHER_TIMEZONE,
                lookback_hours=settings.WEATHER_LOOKBACK_HOURS,
            )

            raw_loaded = load_weather_raw(
                payload=payload,
                batch_id=batch_id,
                run_id=run_id,
                location_name=settings.WEATHER_LOCATION_NAME,
                latitude=settings.WEATHER_LATITUDE,
                longitude=settings.WEATHER_LONGITUDE,
            )

            if raw_loaded <= 0:
                raise RuntimeError("No raw weather records were loaded.")

            logger.info(f"Loaded {raw_loaded} raw weather hourly records.")
            
            return {
                **batch_info,
                "weather_raw_loaded": raw_loaded,
            }

        except Exception as e:
            logger.error(f"Error in extract_and_load_weather task: {e}")
            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Extract and load weather failed: {e}",
            )
            raise

    @task
    def load_calendar(batch_info: dict) -> dict:
        """
        4. Load local calendar CSV into raw tables.
        """
        from src.common.config import get_settings
        from src.load.calendar_raw_loader import load_calendar_raw
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed

        settings = get_settings()
        run_id = batch_info["run_id"]
        batch_id = batch_info["batch_id"]

        try:
            raw_loaded = load_calendar_raw(
                csv_path=settings.CALENDAR_CSV_PATH,
                batch_id=batch_id,
                run_id=run_id,
            )

            if raw_loaded <= 0:
                raise RuntimeError("No raw calendar records were loaded.")

            logger.info(f"Loaded {raw_loaded} raw calendar records.")

            return {
                **batch_info,
                "calendar_raw_loaded": raw_loaded,
            }

        except Exception as e:
            logger.error(f"Error in load_calendar task: {e}")
            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Load calendar failed: {e}",
            )
            raise

    @task
    def transform_weather_and_calendar(batch_info: dict) -> dict:
        """
        5. Transform raw weather/calendar data to staging tables.
        """
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed
        from src.transform.calendar_transformer import transform_calendar
        from src.transform.weather_transformer import transform_weather_hourly

        run_id = batch_info["run_id"]
        batch_id = batch_info["batch_id"]

        try:
            logger.info("Transforming weather hourly staging records...")
            tx_weather = transform_weather_hourly(batch_id)

            logger.info("Transforming calendar staging records...")
            tx_calendar = transform_calendar(batch_id)

            if tx_weather <= 0:
                raise RuntimeError("No weather records were transformed.")
            if tx_calendar <= 0:
                raise RuntimeError("No calendar records were transformed.")

            records_loaded = tx_weather + tx_calendar

            return {
                **batch_info,
                "tx_weather": tx_weather,
                "tx_calendar": tx_calendar,
                "records_loaded": records_loaded,
            }

        except Exception as e:
            logger.error(f"Error in transform_weather_and_calendar task: {e}")
            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Transformation failed: {e}",
            )
            raise

    @task
    def run_dq(batch_info: dict) -> dict:
        """
        6. Execute weather & calendar Data Quality checks.
        """
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed
        from src.quality.weather_calendar_checks import run_weather_calendar_dq_checks

        run_id = batch_info["run_id"]
        batch_id = batch_info["batch_id"]

        try:
            run_weather_calendar_dq_checks(run_id=run_id, batch_id=batch_id)
            return batch_info
        except Exception as e:
            logger.error(f"Error in run_dq task: {e}")
            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"DQ checks failed: {e}",
            )
            raise

    @task
    def update_watermarks(batch_info: dict) -> dict:
        """
        7. Update watermarks for weather and calendar sources.
        """
        from src.common.db import fetch_one
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed
        from src.metadata.watermark_manager import update_watermark

        run_id = batch_info["run_id"]
        batch_id = batch_info["batch_id"]

        try:
            # Weather watermark
            weather_row = fetch_one(
                """
                SELECT MAX(weather_time) AS max_time, MAX(fetched_at) AS max_fetched
                FROM staging.weather_hourly
                WHERE batch_id = :batch_id
                """,
                {"batch_id": batch_id},
            )
            weather_val = None
            if weather_row:
                if weather_row["max_time"]:
                    weather_val = weather_row["max_time"].isoformat()
                elif weather_row["max_fetched"]:
                    weather_val = weather_row["max_fetched"].isoformat()

            if not weather_val:
                weather_val = pendulum.now("UTC").isoformat()

            # Calendar watermark
            cal_row = fetch_one(
                """
                SELECT MAX(calendar_date) AS max_date
                FROM staging.calendar
                WHERE batch_id = :batch_id
                """,
                {"batch_id": batch_id},
            )
            calendar_val = None
            if cal_row and cal_row["max_date"]:
                calendar_val = cal_row["max_date"].isoformat()

            if not calendar_val:
                calendar_val = pendulum.now("UTC").isoformat()

            logger.info(f"Updating weather_hourly watermark: {weather_val}")
            update_watermark("weather_hourly", weather_val)

            logger.info(f"Updating calendar watermark: {calendar_val}")
            update_watermark("calendar", calendar_val)

            return {
                **batch_info,
                "weather_watermark": weather_val,
                "calendar_watermark": calendar_val,
            }

        except Exception as e:
            logger.error(f"Error in update_watermarks task: {e}")
            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Watermarks update failed: {e}",
            )
            raise

    @task
    def finish_pipeline(batch_info: dict) -> None:
        """
        8. Mark pipeline run as success.
        """
        from src.common.db import fetch_one
        from src.metadata.pipeline_run_tracker import (
            finish_pipeline_run_failed,
            finish_pipeline_run_success,
        )

        run_id = batch_info["run_id"]
        records_loaded = batch_info.get("records_loaded", 0)

        # Count total rejected records for this run (if any)
        try:
            rejected_row = fetch_one(
                """
                SELECT COUNT(*) AS rejected_count
                FROM etl_metadata.rejected_records
                WHERE run_id = :run_id
                  AND source_name IN ('weather_hourly', 'calendar')
                """,
                {"run_id": run_id},
            )
            records_rejected = (
                int(rejected_row["rejected_count"])
                if rejected_row and rejected_row["rejected_count"] is not None
                else 0
            )

            finish_pipeline_run_success(
                run_id=run_id,
                # 1 weather feed + 1 calendar CSV file
                records_extracted=2,
                records_loaded=records_loaded,
                records_rejected=records_rejected,
            )

            logger.info(
                f"Weather + Calendar sync pipeline run completed successfully. "
                f"run_id={run_id}"
            )

        except Exception as e:
            logger.error(f"Error in finish_pipeline task: {e}")
            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Finish pipeline run success tracking failed: {e}",
            )
            raise

    # Define execution sequence
    batch_info_flow = start_pipeline()
    batch_info_flow = prepare_batch_for_rerun(batch_info_flow)
    batch_info_flow = extract_and_load_weather(batch_info_flow)
    batch_info_flow = load_calendar(batch_info_flow)
    batch_info_flow = transform_weather_and_calendar(batch_info_flow)
    batch_info_flow = run_dq(batch_info_flow)
    batch_info_flow = update_watermarks(batch_info_flow)
    finish_pipeline(batch_info_flow)


dag_instance = weather_calendar_sync_dag()
