import sys
import pendulum

from src.backfill.backfill_manager import backfill_mart_range
from src.common.db import fetch_one
from src.common.logger import get_logger
from src.metadata.pipeline_run_tracker import (
    start_pipeline_run,
    finish_pipeline_run_success,
    finish_pipeline_run_failed,
)

logger = get_logger(__name__)


def run_backfill_smoke_test():
    """
    Smoke test for manual mart backfill manager.
    """
    logger.info("==========================================================")
    logger.info("Starting Backfill Mart Smoke Test")
    logger.info("==========================================================")

    # 1. Determine a target date/hour that currently has data in staging.station_status
    sql_valid_window = """
        SELECT
            DATE_TRUNC('hour', COALESCE(last_reported, fetched_at)) AS valid_hour,
            CAST(COALESCE(last_reported, fetched_at) AS DATE) AS valid_date
        FROM staging.station_status
        GROUP BY 1, 2
        HAVING COUNT(*) > 100
        ORDER BY valid_hour DESC
        LIMIT 1
    """
    row = fetch_one(sql_valid_window)

    if row and row.get("valid_hour"):
        target_dt = pendulum.instance(row["valid_hour"])
        start_hour = target_dt.format("YYYY-MM-DD HH:mm:ss")
        end_hour = target_dt.add(hours=1).format("YYYY-MM-DD HH:mm:ss")
        target_date = row["valid_date"].strftime("%Y-%m-%d")
    else:
        start_hour = "2026-07-22 07:00:00"
        end_hour = "2026-07-22 08:00:00"
        target_date = "2026-07-22"

    logger.info(f"Targeting window [{start_hour} to {end_hour}] and date {target_date} for backfill smoke test")

    run_id = f"smoke_test_backfill_{pendulum.now('UTC').format('YYYYMMDD_HHmmss')}"
    batch_id = run_id
    dag_id = "backfill_mart_smoke_test"

    start_pipeline_run(run_id=run_id, dag_id=dag_id)

    try:
        summary = backfill_mart_range(
            backfill_type="both",
            start=start_hour,
            end=end_hour,
            batch_id=batch_id,
            run_id=run_id,
        )

        logger.info(f"Backfill summary: {summary}")

        assert summary["backfill_type"] == "both"
        assert summary["hourly_windows_processed"] >= 1
        assert summary["daily_dates_processed"] >= 1
        assert summary["total_records_loaded"] > 0
        assert "daily_station_summary" in summary["daily_rows_loaded_by_table"]
        assert summary["daily_rows_loaded_by_table"]["daily_station_summary"] > 0

        finish_pipeline_run_success(
            run_id=run_id,
            records_extracted=summary["total_windows_or_dates_processed"],
            records_loaded=summary["total_records_loaded"],
            records_rejected=0,
        )

        logger.info("==========================================================")
        logger.info("Backfill Mart Smoke Test PASSED SUCCESSFULLY!")
        logger.info("==========================================================")

    except Exception as e:
        logger.error(f"Backfill Mart Smoke Test FAILED: {e}")
        finish_pipeline_run_failed(run_id=run_id, error_message=str(e))
        sys.exit(1)


if __name__ == "__main__":
    run_backfill_smoke_test()
