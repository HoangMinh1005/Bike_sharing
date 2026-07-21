import uuid
import pendulum

from src.common.config import get_settings
from src.common.db import execute_sql, fetch_one
from src.common.logger import get_logger
from src.extract.weather_client import WeatherClient
from src.load.weather_raw_loader import load_weather_raw
from src.load.calendar_raw_loader import load_calendar_raw
from src.transform.weather_transformer import transform_weather_hourly
from src.transform.calendar_transformer import transform_calendar
from src.quality.weather_calendar_checks import run_weather_calendar_dq_checks
from src.metadata.pipeline_run_tracker import (
    start_pipeline_run,
    finish_pipeline_run_success,
    finish_pipeline_run_failed,
)
from src.metadata.watermark_manager import update_watermark

logger = get_logger(__name__)


def cleanup_batch_records(batch_id: str) -> None:
    """Clean existing raw and staging records for this test batch."""
    logger.info(f"Cleaning test batch: {batch_id}")
    
    execute_sql("DELETE FROM staging.weather_hourly WHERE batch_id = :batch_id", {"batch_id": batch_id})
    execute_sql("DELETE FROM staging.calendar WHERE batch_id = :batch_id", {"batch_id": batch_id})
    execute_sql("DELETE FROM raw.weather_hourly WHERE batch_id = :batch_id", {"batch_id": batch_id})
    execute_sql("DELETE FROM raw.calendar WHERE batch_id = :batch_id", {"batch_id": batch_id})
    execute_sql("DELETE FROM etl_metadata.dq_results WHERE run_id = :batch_id", {"batch_id": batch_id})
    execute_sql("DELETE FROM etl_metadata.rejected_records WHERE run_id = :batch_id", {"batch_id": batch_id})


def run_weather_calendar_smoke_test():
    """
    Execute weather and calendar sync pipeline end-to-end.
    """
    settings = get_settings()
    dag_id = "test_weather_calendar_smoke"
    run_id = f"manual-wc-smoke-{uuid.uuid4()}"
    batch_id = run_id

    logger.info(f"Starting weather_calendar smoke test: run_id={run_id}")

    try:
        # 1. Start pipeline run tracking
        start_pipeline_run(run_id=run_id, dag_id=dag_id)

        # 2. Cleanup batch
        cleanup_batch_records(batch_id)

        # 3. Extract and load weather raw
        weather_client = WeatherClient(settings.WEATHER_API_BASE_URL)
        payload = weather_client.fetch_hourly_weather(
            latitude=settings.WEATHER_LATITUDE,
            longitude=settings.WEATHER_LONGITUDE,
            timezone=settings.WEATHER_TIMEZONE,
            lookback_hours=settings.WEATHER_LOOKBACK_HOURS,
        )
        
        weather_raw_loaded = load_weather_raw(
            payload=payload,
            batch_id=batch_id,
            run_id=run_id,
            location_name=settings.WEATHER_LOCATION_NAME,
            latitude=settings.WEATHER_LATITUDE,
            longitude=settings.WEATHER_LONGITUDE,
        )
        assert weather_raw_loaded > 0, "No raw weather records loaded!"

        # 4. Load calendar raw
        calendar_raw_loaded = load_calendar_raw(
            csv_path=settings.CALENDAR_CSV_PATH,
            batch_id=batch_id,
            run_id=run_id,
        )
        assert calendar_raw_loaded > 0, "No raw calendar records loaded!"

        # 5. Transform staging weather & calendar
        tx_weather = transform_weather_hourly(batch_id)
        tx_calendar = transform_calendar(batch_id)
        assert tx_weather == weather_raw_loaded, "Weather transform count mismatch!"
        assert tx_calendar == calendar_raw_loaded, "Calendar transform count mismatch!"

        # 6. Run DQ checks
        run_weather_calendar_dq_checks(run_id=run_id, batch_id=batch_id)

        # 7. Update smoke test watermarks (use custom sources to prevent staging pollution)
        weather_watermark_val = pendulum.now("UTC").isoformat()
        update_watermark("weather_hourly_smoke_test", weather_watermark_val)

        calendar_watermark_val = pendulum.now("UTC").isoformat()
        update_watermark("calendar_smoke_test", calendar_watermark_val)

        # 8. Complete tracking
        finish_pipeline_run_success(
            run_id=run_id,
            records_extracted=2,
            records_loaded=tx_weather + tx_calendar,
            records_rejected=0,
        )

        logger.info("==========================================================")
        logger.info("Weather + Calendar Smoke Test Summary:")
        logger.info(f"  - Run ID: {run_id}")
        logger.info(f"  - Batch ID: {batch_id}")
        logger.info(f"  - Raw weather loaded: {weather_raw_loaded}")
        logger.info(f"  - Raw calendar loaded: {calendar_raw_loaded}")
        logger.info(f"  - Staging weather loaded: {tx_weather}")
        logger.info(f"  - Staging calendar loaded: {tx_calendar}")
        logger.info("==========================================================")
        logger.info("Weather + Calendar ETL smoke test completed successfully.")

    except Exception as e:
        logger.error(f"Smoke test failed: {e}")
        finish_pipeline_run_failed(run_id=run_id, error_message=str(e))
        raise
    finally:
        # Clean up database test records to keep schema pristine
        cleanup_batch_records(batch_id)


if __name__ == "__main__":
    run_weather_calendar_smoke_test()
