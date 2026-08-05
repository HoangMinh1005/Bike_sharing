import pytest
import warnings

from src.common.db import fetch_all, fetch_one
from src.common.logger import get_logger

logger = get_logger(__name__)


def query_count(table_name: str) -> int:
    """
    Helper function to query row count of a table.
    """
    sql = f"SELECT COUNT(*) AS row_count FROM {table_name}"
    res = fetch_one(sql)
    return int(res["row_count"] or 0) if res else 0


def assert_table_has_rows(table_name: str, min_rows: int = 1) -> int:
    """
    Helper function to assert a table has at least min_rows.
    """
    count = query_count(table_name)
    assert count >= min_rows, f"Table '{table_name}' is empty or has fewer than {min_rows} rows (count={count})."
    return count


def test_raw_layer_has_data():
    """
    1. Verify raw layer tables contain data.
    """
    assert_table_has_rows("raw.gbfs_feed_snapshots")
    assert_table_has_rows("raw.station_status_snapshots")
    assert_table_has_rows("raw.weather_hourly")
    assert_table_has_rows("raw.calendar")


def test_staging_layer_has_data():
    """
    2. Verify staging layer tables contain data.
    """
    assert_table_has_rows("staging.stations")
    assert_table_has_rows("staging.station_status")
    assert_table_has_rows("staging.weather_hourly")
    assert_table_has_rows("staging.calendar")


def test_hourly_mart_layer_has_data():
    """
    3. Verify hourly mart layer tables contain data.
    """
    assert_table_has_rows("mart.hourly_station_availability")
    assert_table_has_rows("mart.hourly_region_availability")
    assert_table_has_rows("mart.weather_mobility_summary")

    # vehicle_type_availability_summary is optional if vehicle_types feed is not supplied
    vt_count = query_count("mart.vehicle_type_availability_summary")
    if vt_count == 0:
        warnings.warn("mart.vehicle_type_availability_summary is empty (vehicle_types data is optional).")


def test_daily_mart_layer_has_data():
    """
    4. Verify daily mart layer tables contain data.
    """
    assert_table_has_rows("mart.daily_station_summary")
    assert_table_has_rows("mart.daily_region_summary")
    assert_table_has_rows("mart.daily_system_summary")
    assert_table_has_rows("mart.station_demand_ranking")


def test_metadata_layer_has_data():
    """
    5. Verify etl_metadata tracking tables contain data.
    """
    assert_table_has_rows("etl_metadata.pipeline_runs")
    assert_table_has_rows("etl_metadata.dq_results")
    assert_table_has_rows("etl_metadata.watermarks")
    assert_table_has_rows("etl_metadata.pipeline_health_summary")


def test_latest_summary_date_consistency():
    """
    6. Verify latest summary_date in daily mart tables is non-empty and consistent.
    """
    res = fetch_one("SELECT MAX(summary_date) AS latest_date FROM mart.daily_system_summary")
    assert res is not None and res.get("latest_date") is not None, "mart.daily_system_summary has no summary_date."

    latest_date = str(res["latest_date"])
    params = {"latest_date": latest_date}

    # Station summary for latest_date
    st_res = fetch_one(
        "SELECT COUNT(*) AS count FROM mart.daily_station_summary WHERE summary_date = CAST(:latest_date AS DATE)",
        params,
    )
    assert int(st_res["count"]) > 0, f"No daily_station_summary records found for latest_date={latest_date}"

    # Region summary for latest_date
    rg_res = fetch_one(
        "SELECT COUNT(*) AS count FROM mart.daily_region_summary WHERE summary_date = CAST(:latest_date AS DATE)",
        params,
    )
    assert int(rg_res["count"]) > 0, f"No daily_region_summary records found for latest_date={latest_date}"

    # Demand ranking for latest_date
    rk_res = fetch_one(
        "SELECT COUNT(*) AS count FROM mart.station_demand_ranking WHERE ranking_date = CAST(:latest_date AS DATE)",
        params,
    )
    assert int(rk_res["count"]) > 0, f"No station_demand_ranking records found for latest_date={latest_date}"

    # System summary for latest_date
    sys_res = fetch_one(
        "SELECT COUNT(*) AS count FROM mart.daily_system_summary WHERE summary_date = CAST(:latest_date AS DATE)",
        params,
    )
    assert int(sys_res["count"]) >= 1, f"No daily_system_summary record found for latest_date={latest_date}"


def test_mart_metric_boundaries():
    """
    7. Validate basic metric boundaries in mart tables.
    """
    # Check rates in hourly station availability
    sql_rates = """
        SELECT
            MIN(availability_rate) AS min_avail,
            MAX(availability_rate) AS max_avail,
            MIN(dock_utilization_rate) AS min_util,
            MAX(dock_utilization_rate) AS max_util
        FROM mart.hourly_station_availability
        WHERE availability_rate IS NOT NULL AND dock_utilization_rate IS NOT NULL
    """
    rates = fetch_one(sql_rates)
    if rates and rates.get("min_avail") is not None:
        assert float(rates["min_avail"]) >= 0.0, "Found negative availability_rate in hourly station mart."
        assert float(rates["max_avail"]) <= 1.0, "Found availability_rate > 1.0 in hourly station mart."
        assert float(rates["min_util"]) >= 0.0, "Found negative dock_utilization_rate in hourly station mart."
        assert float(rates["max_util"]) <= 1.0, "Found dock_utilization_rate > 1.0 in hourly station mart."

    # Check daily station metrics
    sql_daily = """
        SELECT
            MIN(active_hour_count) AS min_active_hours,
            MIN(total_observation_count) AS min_obs
        FROM mart.daily_station_summary
    """
    daily = fetch_one(sql_daily)
    if daily and daily.get("min_active_hours") is not None:
        assert int(daily["min_active_hours"]) >= 0, "Found negative active_hour_count in daily station summary."
        assert int(daily["min_obs"]) >= 0, "Found negative total_observation_count in daily station summary."

    # Check ranking metrics
    sql_ranking = """
        SELECT
            MIN(demand_score) AS min_score,
            MIN(demand_rank) AS min_rank
        FROM mart.station_demand_ranking
    """
    ranking = fetch_one(sql_ranking)
    if ranking and ranking.get("min_score") is not None:
        assert float(ranking["min_score"]) >= 0.0, "Found negative demand_score in station_demand_ranking."
        assert int(ranking["min_rank"]) > 0, "Found demand_rank <= 0 in station_demand_ranking."

    print("\nEND-TO-END VALIDATION PASSED")
