import uuid
import pendulum

from src.common.db import execute_sql, fetch_one
from src.common.logger import get_logger
from src.mart.daily_mart_builder import (
    build_daily_station_summary,
    build_daily_region_summary,
    build_station_demand_ranking,
    build_daily_system_summary,
)
from src.metadata.pipeline_run_tracker import (
    start_pipeline_run,
    finish_pipeline_run_success,
    finish_pipeline_run_failed,
)
from src.metadata.watermark_manager import update_watermark
from src.quality.daily_mart_checks import run_daily_mart_dq_checks

logger = get_logger(__name__)


def run_daily_summary_smoke_test():
    """
    Execute end-to-end smoke test for daily summary pipeline using existing hourly mart data.
    """
    dag_id = "test_daily_summary_smoke"
    run_id = f"manual-daily-summary-smoke-{uuid.uuid4()}"
    batch_id = run_id

    logger.info(f"Starting daily summary smoke test: run_id={run_id}")

    try:
        # 1. Start pipeline run tracking
        start_pipeline_run(run_id=run_id, dag_id=dag_id)

        # 2. Determine target date from latest mart.hourly_station_availability date
        latest_row = fetch_one(
            """
            SELECT MAX(DATE(hour_bucket)) AS max_date
            FROM mart.hourly_station_availability
            """
        )

        if latest_row and latest_row["max_date"]:
            target_date = latest_row["max_date"].strftime("%Y-%m-%d")
        else:
            target_date = pendulum.now("UTC").subtract(days=1).to_date_string()

        logger.info(f"Target date for smoke test: {target_date}")

        # 3. Clean existing daily mart records for target_date
        params = {"target_date": target_date}
        execute_sql("DELETE FROM mart.daily_system_summary WHERE summary_date = CAST(:target_date AS DATE)", params)
        execute_sql("DELETE FROM mart.station_demand_ranking WHERE ranking_date = CAST(:target_date AS DATE)", params)
        execute_sql("DELETE FROM mart.daily_region_summary WHERE summary_date = CAST(:target_date AS DATE)", params)
        execute_sql("DELETE FROM mart.daily_station_summary WHERE summary_date = CAST(:target_date AS DATE)", params)

        # 4. Build daily mart tables
        station_mart = build_daily_station_summary(target_date, batch_id, run_id)
        region_mart = build_daily_region_summary(target_date, batch_id, run_id)
        ranking_mart = build_station_demand_ranking(target_date, batch_id, run_id)
        system_mart = build_daily_system_summary(target_date, batch_id, run_id)

        # 5. Run DQ checks
        run_daily_mart_dq_checks(
            run_id=run_id,
            batch_id=batch_id,
            target_date=target_date,
        )

        # 6. Update smoke test watermark
        update_watermark("daily_summary_smoke_test", target_date)

        # 7. Complete pipeline tracking
        total_loaded = station_mart + region_mart + ranking_mart + system_mart
        finish_pipeline_run_success(
            run_id=run_id,
            records_extracted=4,
            records_loaded=total_loaded,
            records_rejected=0,
        )

        logger.info("==========================================================")
        logger.info("Daily Summary Smoke Test Summary:")
        logger.info(f"  - Run ID: {run_id}")
        logger.info(f"  - Target Date: {target_date}")
        logger.info(f"  - Daily Station Summary rows: {station_mart}")
        logger.info(f"  - Daily Region Summary rows: {region_mart}")
        logger.info(f"  - Station Demand Ranking rows: {ranking_mart}")
        logger.info(f"  - Daily System Summary rows: {system_mart}")
        logger.info(f"  - Total Daily Mart records loaded: {total_loaded}")
        logger.info("==========================================================")
        logger.info("Daily Summary ETL smoke test completed successfully.")

    except Exception as e:
        logger.error(f"Daily summary smoke test failed: {e}")
        finish_pipeline_run_failed(run_id=run_id, error_message=str(e))
        raise


if __name__ == "__main__":
    run_daily_summary_smoke_test()
