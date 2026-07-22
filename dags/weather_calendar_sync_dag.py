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

        This makes the DAG idempotent when the same Airflow run is cleared
        and executed again.
        """
        from src.common.db import execute_sql
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed

        run_id = batch_info["run_id"]
        batch_id = batch_info["batch_id"]

        try:
            logger.info(
                f"Cleaning existing weather/calendar records for batch_id={batch_id}"
            )

            deleted_staging_weather = execute_sql(
                """
                DELETE FROM staging.weather_hourly
                WHERE batch_id = :batch_id
                """,
                {
                    "batch_id": batch_id,
                },
            )

            deleted_staging_calendar = execute_sql(
                """
                DELETE FROM staging.calendar
                WHERE batch_id = :batch_id
                """,
                {
                    "batch_id": batch_id,
                },
            )

            deleted_raw_weather = execute_sql(
                """
                DELETE FROM raw.weather_hourly
                WHERE batch_id = :batch_id
                """,
                {
                    "batch_id": batch_id,
                },
            )

            deleted_raw_calendar = execute_sql(
                """
                DELETE FROM raw.calendar
                WHERE batch_id = :batch_id
                """,
                {
                    "batch_id": batch_id,
                },
            )

            logger.info(
                f"Deleted existing records for batch_id={batch_id}: "
                f"staging.weather_hourly={deleted_staging_weather}, "
                f"staging.calendar={deleted_staging_calendar}, "
                f"raw.weather_hourly={deleted_raw_weather}, "
                f"raw.calendar={deleted_raw_calendar}"
            )

            return batch_info

        except Exception as e:
            logger.error(f"Error in prepare_batch_for_rerun task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Prepare weather/calendar batch for rerun failed: {e}",
            )

            raise

    @task
    def extract_and_load_weather(batch_info: dict) -> dict:
        """
        3. Fetch hourly weather data from Open-Meteo and load raw records.
        """
        from src.common.config import get_settings
        from src.extract.weather_client import WeatherClient
        from src.load.weather_raw_loader import load_weather_raw
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed

        settings = get_settings()

        run_id = batch_info["run_id"]
        batch_id = batch_info["batch_id"]

        try:
            logger.info(
                f"Fetching hourly weather data. "
                f"location={settings.WEATHER_LOCATION_NAME}, "
                f"lat={settings.WEATHER_LATITUDE}, "
                f"lon={settings.WEATHER_LONGITUDE}, "
                f"timezone={settings.WEATHER_TIMEZONE}, "
                f"lookback_hours={settings.WEATHER_LOOKBACK_HOURS}"
            )

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

            logger.info(
                f"Raw weather loading completed successfully. "
                f"raw_weather_records_loaded={raw_loaded}"
            )

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
        4. Load local calendar CSV into raw.calendar.
        """
        from src.common.config import get_settings
        from src.load.calendar_raw_loader import load_calendar_raw
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed

        settings = get_settings()

        run_id = batch_info["run_id"]
        batch_id = batch_info["batch_id"]

        try:
            logger.info(
                f"Loading calendar CSV into raw layer. "
                f"csv_path={settings.CALENDAR_CSV_PATH}"
            )

            raw_loaded = load_calendar_raw(
                csv_path=settings.CALENDAR_CSV_PATH,
                batch_id=batch_id,
                run_id=run_id,
            )

            if raw_loaded <= 0:
                raise RuntimeError("No raw calendar records were loaded.")

            logger.info(
                f"Raw calendar loading completed successfully. "
                f"raw_calendar_records_loaded={raw_loaded}"
            )

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
            logger.info("Transforming raw.weather_hourly to staging.weather_hourly...")
            transformed_weather = transform_weather_hourly(batch_id)

            logger.info("Transforming raw.calendar to staging.calendar...")
            transformed_calendar = transform_calendar(batch_id)

            if transformed_weather <= 0:
                raise RuntimeError("No weather records were transformed.")

            if transformed_calendar <= 0:
                raise RuntimeError("No calendar records were transformed.")

            records_loaded = transformed_weather + transformed_calendar

            logger.info(
                f"Weather/calendar transformation completed successfully. "
                f"weather={transformed_weather}, "
                f"calendar={transformed_calendar}, "
                f"records_loaded={records_loaded}"
            )

            return {
                **batch_info,
                "transformed_weather": transformed_weather,
                "transformed_calendar": transformed_calendar,
                "records_loaded": records_loaded,
            }

        except Exception as e:
            logger.error(f"Error in transform_weather_and_calendar task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Weather/calendar transformation failed: {e}",
            )

            raise

    @task
    def run_dq(batch_info: dict) -> dict:
        """
        6. Execute weather and calendar Data Quality checks.
        """
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed
        from src.quality.weather_calendar_checks import run_weather_calendar_dq_checks

        run_id = batch_info["run_id"]
        batch_id = batch_info["batch_id"]

        try:
            logger.info(
                f"Running weather/calendar DQ checks. "
                f"run_id={run_id}, batch_id={batch_id}"
            )

            run_weather_calendar_dq_checks(
                run_id=run_id,
                batch_id=batch_id,
            )

            logger.info("Weather/calendar DQ checks completed successfully.")

            return batch_info

        except Exception as e:
            logger.error(f"Error in run_dq task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Weather/calendar DQ checks failed: {e}",
            )

            raise

    @task
    def update_watermarks(batch_info: dict) -> dict:
        """
        7. Update watermarks for weather_hourly and calendar sources.

        Weather watermark priority:
        1. MAX(weather_time)
        2. MAX(fetched_at)
        3. current UTC timestamp

        Calendar watermark priority:
        1. MAX(calendar_date)
        2. current UTC timestamp
        """
        from src.common.db import fetch_one
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed
        from src.metadata.watermark_manager import update_watermark

        run_id = batch_info["run_id"]
        batch_id = batch_info["batch_id"]

        try:
            weather_row = fetch_one(
                """
                SELECT
                    MAX(weather_time) AS max_weather_time,
                    MAX(fetched_at) AS max_fetched_at
                FROM staging.weather_hourly
                WHERE batch_id = :batch_id
                """,
                {
                    "batch_id": batch_id,
                },
            )

            weather_watermark = None

            if weather_row:
                if weather_row["max_weather_time"]:
                    weather_watermark = weather_row["max_weather_time"].isoformat()
                elif weather_row["max_fetched_at"]:
                    weather_watermark = weather_row["max_fetched_at"].isoformat()

            if not weather_watermark:
                weather_watermark = pendulum.now("UTC").isoformat()

            calendar_row = fetch_one(
                """
                SELECT
                    MAX(calendar_date) AS max_calendar_date
                FROM staging.calendar
                WHERE batch_id = :batch_id
                """,
                {
                    "batch_id": batch_id,
                },
            )

            calendar_watermark = None

            if calendar_row and calendar_row["max_calendar_date"]:
                calendar_watermark = calendar_row["max_calendar_date"].isoformat()

            if not calendar_watermark:
                calendar_watermark = pendulum.now("UTC").isoformat()

            logger.info(
                f"Updating weather_hourly watermark. "
                f"value={weather_watermark}"
            )

            update_watermark(
                source_name="weather_hourly",
                last_successful_value=weather_watermark,
            )

            logger.info(
                f"Updating calendar watermark. "
                f"value={calendar_watermark}"
            )

            update_watermark(
                source_name="calendar",
                last_successful_value=calendar_watermark,
            )

            return {
                **batch_info,
                "weather_watermark": weather_watermark,
                "calendar_watermark": calendar_watermark,
            }

        except Exception as e:
            logger.error(f"Error in update_watermarks task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Weather/calendar watermarks update failed: {e}",
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

        weather_raw_loaded = batch_info.get("weather_raw_loaded", 0)
        calendar_raw_loaded = batch_info.get("calendar_raw_loaded", 0)
        records_loaded = batch_info.get("records_loaded", 0)

        try:
            rejected_row = fetch_one(
                """
                SELECT COUNT(*) AS rejected_count
                FROM etl_metadata.rejected_records
                WHERE run_id = :run_id
                  AND (
                      source_name IN (
                          'weather_hourly',
                          'calendar',
                          'open_meteo'
                      )
                      OR table_name IN (
                          'raw.weather_hourly',
                          'raw.calendar',
                          'staging.weather_hourly',
                          'staging.calendar'
                      )
                  )
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
                f"Marking weather/calendar pipeline run as success. "
                f"run_id={run_id}, "
                f"weather_raw_loaded={weather_raw_loaded}, "
                f"calendar_raw_loaded={calendar_raw_loaded}, "
                f"records_loaded={records_loaded}, "
                f"records_rejected={records_rejected}"
            )

            finish_pipeline_run_success(
                run_id=run_id,
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
                error_message=f"Finish weather/calendar pipeline tracking failed: {e}",
            )

            raise

    batch_info_flow = start_pipeline()
    batch_info_flow = prepare_batch_for_rerun(batch_info_flow)
    batch_info_flow = extract_and_load_weather(batch_info_flow)
    batch_info_flow = load_calendar(batch_info_flow)
    batch_info_flow = transform_weather_and_calendar(batch_info_flow)
    batch_info_flow = run_dq(batch_info_flow)
    batch_info_flow = update_watermarks(batch_info_flow)
    finish_pipeline(batch_info_flow)


dag_instance = weather_calendar_sync_dag()