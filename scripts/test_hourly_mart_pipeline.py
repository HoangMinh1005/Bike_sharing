import uuid
import pendulum

from src.common.db import execute_sql, fetch_one
from src.common.logger import get_logger
from src.mart.hourly_mart_builder import (
    build_hourly_station_availability,
    build_hourly_region_availability,
    build_vehicle_type_availability_summary,
    build_weather_mobility_summary,
)
from src.metadata.pipeline_run_tracker import (
    start_pipeline_run,
    finish_pipeline_run_success,
    finish_pipeline_run_failed,
)
from src.metadata.watermark_manager import update_watermark
from src.quality.hourly_mart_checks import run_hourly_mart_dq_checks

logger = get_logger(__name__)


def run_hourly_mart_smoke_test():
    """
    Execute end-to-end smoke test for hourly mart pipeline using existing staging data.
    """
    dag_id = "test_hourly_mart_smoke"
    run_id = f"manual-hourly-mart-smoke-{uuid.uuid4()}"
    batch_id = run_id

    logger.info(f"Starting hourly mart smoke test: run_id={run_id}")

    try:
        # 1. Start pipeline run tracking
        start_pipeline_run(run_id=run_id, dag_id=dag_id)

        # 2. Determine target hour from latest staging.station_status timestamp
        latest_row = fetch_one(
            """
            SELECT date_trunc('hour', MAX(COALESCE(last_reported, fetched_at))) AS max_hour
            FROM staging.station_status
            """
        )

        if latest_row and latest_row["max_hour"]:
            target_start_dt = pendulum.instance(latest_row["max_hour"])
        else:
            target_start_dt = pendulum.now("UTC").subtract(hours=1).replace(minute=0, second=0, microsecond=0)

        target_end_dt = target_start_dt.add(hours=1)

        target_hour_start = target_start_dt.to_iso8601_string()
        target_hour_end = target_end_dt.to_iso8601_string()

        logger.info(
            f"Target window for smoke test: "
            f"start={target_hour_start}, end={target_hour_end}"
        )

        # 3. Clean existing mart records in target window
        params = {
            "target_hour_start": target_hour_start,
            "target_hour_end": target_hour_end,
        }

        execute_sql("DELETE FROM mart.weather_mobility_summary WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP) AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)", params)
        execute_sql("DELETE FROM mart.vehicle_type_availability_summary WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP) AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)", params)
        execute_sql("DELETE FROM mart.hourly_region_availability WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP) AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)", params)
        execute_sql("DELETE FROM mart.hourly_station_availability WHERE hour_bucket >= CAST(:target_hour_start AS TIMESTAMP) AND hour_bucket < CAST(:target_hour_end AS TIMESTAMP)", params)

        # 4. Build mart tables
        station_mart = build_hourly_station_availability(target_hour_start, target_hour_end, batch_id, run_id)
        region_mart = build_hourly_region_availability(target_hour_start, target_hour_end, batch_id, run_id)
        vt_mart = build_vehicle_type_availability_summary(target_hour_start, target_hour_end, batch_id, run_id)
        weather_mart = build_weather_mobility_summary(target_hour_start, target_hour_end, batch_id, run_id)

        # 5. Run DQ checks
        run_hourly_mart_dq_checks(
            run_id=run_id,
            batch_id=batch_id,
            target_hour_start=target_hour_start,
            target_hour_end=target_hour_end,
        )

        # 6. Update smoke test watermark
        update_watermark("hourly_mart_smoke_test", target_hour_end)

        # 7. Complete pipeline tracking
        total_loaded = station_mart + region_mart + vt_mart + weather_mart
        finish_pipeline_run_success(
            run_id=run_id,
            records_extracted=4,
            records_loaded=total_loaded,
            records_rejected=0,
        )

        logger.info("==========================================================")
        logger.info("Hourly Mart Smoke Test Summary:")
        logger.info(f"  - Run ID: {run_id}")
        logger.info(f"  - Target Window: [{target_hour_start} to {target_hour_end}]")
        logger.info(f"  - Station Availability Mart rows: {station_mart}")
        logger.info(f"  - Region Availability Mart rows: {region_mart}")
        logger.info(f"  - Vehicle Type Summary Mart rows: {vt_mart}")
        logger.info(f"  - Weather Mobility Summary Mart rows: {weather_mart}")
        logger.info(f"  - Total Mart records loaded: {total_loaded}")
        logger.info("==========================================================")
        logger.info("Hourly Mart ETL smoke test completed successfully.")

    except Exception as e:
        logger.error(f"Hourly mart smoke test failed: {e}")
        finish_pipeline_run_failed(run_id=run_id, error_message=str(e))
        raise


if __name__ == "__main__":
    run_hourly_mart_smoke_test()
