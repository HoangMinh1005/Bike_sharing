import pendulum
import pytest

from src.backfill.backfill_manager import (
    parse_backfill_conf,
    generate_hourly_windows,
    generate_daily_dates,
    backfill_mart_range,
)
from src.cleanup.retention_manager import (
    RETENTION_POLICIES,
    _is_allowed_retention_target,
    cleanup_table_by_retention,
    run_retention_cleanup,
)
from src.common.db import fetch_one


def test_parse_backfill_conf_valid():
    conf = {
        "backfill_type": "hourly",
        "start": "2026-07-01T00:00:00",
        "end": "2026-07-02T00:00:00",
    }
    parsed = parse_backfill_conf(conf)
    assert parsed["backfill_type"] == "hourly"
    assert parsed["start_date"] == "2026-07-01"
    assert parsed["end_date"] == "2026-07-02"


def test_parse_backfill_conf_invalid_type():
    conf = {
        "backfill_type": "invalid_type",
        "start": "2026-07-01",
        "end": "2026-07-02",
    }
    with pytest.raises(ValueError, match="Invalid backfill_type"):
        parse_backfill_conf(conf)


def test_parse_backfill_conf_invalid_range():
    # start >= end
    conf = {
        "backfill_type": "daily",
        "start": "2026-07-05",
        "end": "2026-07-01",
    }
    with pytest.raises(ValueError, match="(?:must be earlier than|cannot be greater than)"):
        parse_backfill_conf(conf)

    # Exceeds max limit for hourly (> 31 days)
    conf_exceed = {
        "backfill_type": "hourly",
        "start": "2026-01-01T00:00:00",
        "end": "2026-03-01T00:00:00",
    }
    with pytest.raises(ValueError, match="(?:exceeds maximum allowed limit of 31 days|must not exceed 31 days)"):
        parse_backfill_conf(conf_exceed)


def test_generate_hourly_windows():
    start_dt = pendulum.datetime(2026, 7, 1, 0, 0, 0, tz="UTC")
    end_dt = pendulum.datetime(2026, 7, 1, 3, 0, 0, tz="UTC")
    windows = generate_hourly_windows(start_dt, end_dt)
    assert len(windows) == 3
    assert windows[0] == ("2026-07-01 00:00:00", "2026-07-01 01:00:00")
    assert windows[2] == ("2026-07-01 02:00:00", "2026-07-01 03:00:00")


def test_generate_daily_dates():
    dates = generate_daily_dates("2026-07-01", "2026-07-03")
    assert dates == ["2026-07-01", "2026-07-02", "2026-07-03"]


def test_retention_whitelist_protection():
    # Valid allowed entry
    assert _is_allowed_retention_target("raw.gbfs_feed_snapshots", "fetched_at", 30) is True

    # Reject unallowed table/column combination
    assert _is_allowed_retention_target("public.users", "created_at", 30) is False
    assert _is_allowed_retention_target("raw.gbfs_feed_snapshots", "id", 30) is False

    with pytest.raises(ValueError, match="Unauthorized retention cleanup target"):
        cleanup_table_by_retention("public.arbitrary_table", "id", 30, dry_run=True)


def test_run_retention_cleanup_dry_run():
    summary = run_retention_cleanup(dry_run=True, enabled_only=True)
    assert summary["dry_run"] is True
    assert summary["tables_processed"] > 0
    assert summary["successful_tables"] > 0
    assert summary["failed_tables"] == 0
    assert summary["total_rows_affected"] >= 0


def test_backfill_mart_range_execution():
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
    else:
        start_hour = "2026-07-22 07:00:00"
        end_hour = "2026-07-22 08:00:00"

    run_id = f"test_backfill_run_{pendulum.now('UTC').format('YYYYMMDD_HHmmss')}"
    batch_id = run_id

    summary = backfill_mart_range(
        backfill_type="both",
        start=start_hour,
        end=end_hour,
        batch_id=batch_id,
        run_id=run_id,
    )

    assert summary["backfill_type"] == "both"
    assert summary["hourly_windows_processed"] == 1
    assert summary["daily_dates_processed"] == 1
    assert summary["total_records_loaded"] > 0
