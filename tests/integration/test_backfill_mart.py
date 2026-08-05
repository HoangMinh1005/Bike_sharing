import uuid
import pendulum
import pytest

from src.backfill.backfill_manager import backfill_mart_range
from src.common.db import fetch_one
from src.common.logger import get_logger

logger = get_logger(__name__)


def test_backfill_mart_hourly_range_smoke():
    """
    Smoke test for backfill_mart_range with a single 1-hour window.
    """
    # 1. Dynamically find a valid hour that has source staging station status data
    sql_valid_hour = """
        SELECT
            DATE_TRUNC('hour', COALESCE(last_reported, fetched_at)) AS valid_hour
        FROM staging.station_status
        GROUP BY 1
        HAVING COUNT(*) > 50
        ORDER BY valid_hour DESC
        LIMIT 1
    """
    row = fetch_one(sql_valid_hour)

    if not row or not row.get("valid_hour"):
        pytest.skip("No staging station status data found in database. Skipping backfill smoke test.")

    valid_dt = pendulum.instance(row["valid_hour"])
    start_hour = valid_dt.format("YYYY-MM-DD HH:mm:ss")
    end_hour = valid_dt.add(hours=1).format("YYYY-MM-DD HH:mm:ss")

    logger.info(f"Running backfill mart smoke test for window [{start_hour} to {end_hour})")

    run_id = f"manual-backfill-smoke-{uuid.uuid4().hex[:8]}"
    batch_id = run_id

    summary = backfill_mart_range(
        backfill_type="hourly",
        start=start_hour,
        end=end_hour,
        batch_id=batch_id,
        run_id=run_id,
        include_partition_details=True,
    )

    print(f"\nBackfill Mart Smoke Test Summary: {summary}")

    assert summary["backfill_type"] == "hourly"
    assert summary["hourly_windows_processed"] == 1
    assert summary["total_records_loaded"] > 0
    assert summary["hourly_rows_loaded_by_table"]["hourly_station_availability"] > 0
