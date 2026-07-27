import uuid
import pytest
import pendulum

from src.common.db import execute_sql, fetch_one, fetch_all
from src.mart.daily_mart_builder import (
    build_daily_station_summary,
    build_daily_region_summary,
    build_station_demand_ranking,
    build_daily_system_summary,
)
from src.quality.daily_mart_checks import run_daily_mart_dq_checks


@pytest.fixture
def clean_daily_test_dates():
    dates = []
    yield dates
    for target_date in dates:
        params = {"target_date": target_date}
        execute_sql("DELETE FROM mart.daily_system_summary WHERE summary_date = CAST(:target_date AS DATE)", params)
        execute_sql("DELETE FROM mart.station_demand_ranking WHERE ranking_date = CAST(:target_date AS DATE)", params)
        execute_sql("DELETE FROM mart.daily_region_summary WHERE summary_date = CAST(:target_date AS DATE)", params)
        execute_sql("DELETE FROM mart.daily_station_summary WHERE summary_date = CAST(:target_date AS DATE)", params)
        execute_sql("DELETE FROM mart.hourly_station_availability WHERE DATE(hour_bucket) = CAST(:target_date AS DATE)", params)


def test_daily_mart_builder_invalid_date():
    """Verify that invalid target dates raise ValueError."""
    target_date = "invalid-date-string"
    batch_id = f"test-invalid-{uuid.uuid4()}"

    with pytest.raises(ValueError):
        build_daily_station_summary(target_date, batch_id, batch_id)

    with pytest.raises(ValueError):
        build_daily_region_summary(target_date, batch_id, batch_id)

    with pytest.raises(ValueError):
        build_station_demand_ranking(target_date, batch_id, batch_id)

    with pytest.raises(ValueError):
        build_daily_system_summary(target_date, batch_id, batch_id)


def test_daily_mart_builder_end_to_end_flow(clean_daily_test_dates):
    """Test full daily mart building flow with mock hourly station availability data."""
    batch_id = f"test-daily-mart-{uuid.uuid4()}"
    run_id = batch_id
    target_date = "2026-07-20"
    clean_daily_test_dates.append(target_date)

    try:
        # Insert mock hourly_station_availability records for station 1 (High demand: low availability)
        for hour in range(24):
            hour_str = f"{hour:02d}"
            hour_bucket = f"{target_date}T{hour_str}:00:00"
            execute_sql(
                """
                INSERT INTO mart.hourly_station_availability (
                    hour_bucket, station_id, station_name, region_id, region_name,
                    latitude, longitude, capacity, observation_count, avg_bikes_available,
                    avg_docks_available, avg_bikes_disabled, avg_docks_disabled,
                    min_bikes_available, max_bikes_available, empty_observation_count,
                    full_observation_count, availability_rate, dock_utilization_rate,
                    is_installed, is_renting, is_returning, temperature, humidity,
                    precipitation, wind_speed, weather_code, calendar_date, day_of_week,
                    is_weekend, is_holiday, holiday_name, batch_id, run_id
                ) VALUES (
                    CAST(:hour_bucket AS TIMESTAMP), 'st-daily-01', 'Station High Demand', 'reg-daily-01', 'Region 01',
                    40.7128, -74.0060, 20, 10, 1.0,
                    19.0, 0, 0, 0, 2, 5,
                    0, 0.05, 0.95,
                    true, true, true, 25.0, 60.0,
                    0.0, 10.0, 800, CAST(:target_date AS DATE), 'Monday',
                    false, false, NULL, :batch_id, :run_id
                )
                ON CONFLICT (hour_bucket, station_id) DO NOTHING
                """,
                {"hour_bucket": hour_bucket, "target_date": target_date, "batch_id": batch_id, "run_id": run_id},
            )

        # Insert mock hourly_station_availability records for station 2 (Normal demand)
        for hour in range(24):
            hour_str = f"{hour:02d}"
            hour_bucket = f"{target_date}T{hour_str}:00:00"
            execute_sql(
                """
                INSERT INTO mart.hourly_station_availability (
                    hour_bucket, station_id, station_name, region_id, region_name,
                    latitude, longitude, capacity, observation_count, avg_bikes_available,
                    avg_docks_available, avg_bikes_disabled, avg_docks_disabled,
                    min_bikes_available, max_bikes_available, empty_observation_count,
                    full_observation_count, availability_rate, dock_utilization_rate,
                    is_installed, is_renting, is_returning, temperature, humidity,
                    precipitation, wind_speed, weather_code, calendar_date, day_of_week,
                    is_weekend, is_holiday, holiday_name, batch_id, run_id
                ) VALUES (
                    CAST(:hour_bucket AS TIMESTAMP), 'st-daily-02', 'Station Normal', 'reg-daily-01', 'Region 01',
                    40.7130, -74.0070, 20, 10, 10.0,
                    10.0, 0, 0, 8, 12, 0,
                    0, 0.50, 0.50,
                    true, true, true, 25.0, 60.0,
                    0.0, 10.0, 800, CAST(:target_date AS DATE), 'Monday',
                    false, false, NULL, :batch_id, :run_id
                )
                ON CONFLICT (hour_bucket, station_id) DO NOTHING
                """,
                {"hour_bucket": hour_bucket, "target_date": target_date, "batch_id": batch_id, "run_id": run_id},
            )

        # 1. Build Daily Station Summary
        count_dss = build_daily_station_summary(target_date, batch_id, run_id)
        assert count_dss == 2

        # Verify daily station summary values
        dss_01 = fetch_one(
            "SELECT * FROM mart.daily_station_summary WHERE summary_date = CAST(:target_date AS DATE) AND station_id = 'st-daily-01'",
            {"target_date": target_date},
        )
        assert dss_01 is not None
        assert dss_01["active_hour_count"] == 24
        assert dss_01["low_availability_hour_count"] == 24
        assert float(dss_01["avg_availability_rate"]) == 0.05

        # 2. Build Daily Region Summary
        count_drs = build_daily_region_summary(target_date, batch_id, run_id)
        assert count_drs == 1

        drs_reg = fetch_one(
            "SELECT * FROM mart.daily_region_summary WHERE summary_date = CAST(:target_date AS DATE) AND region_id = 'reg-daily-01'",
            {"target_date": target_date},
        )
        assert drs_reg is not None
        assert drs_reg["station_count"] == 2
        assert drs_reg["active_station_count"] == 2

        # 3. Build Station Demand Ranking
        count_sdr = build_station_demand_ranking(target_date, batch_id, run_id)
        assert count_sdr == 2

        sdr_rank_1 = fetch_one(
            "SELECT * FROM mart.station_demand_ranking WHERE ranking_date = CAST(:target_date AS DATE) AND demand_rank = 1",
            {"target_date": target_date},
        )
        assert sdr_rank_1 is not None
        assert sdr_rank_1["station_id"] == "st-daily-01"
        assert sdr_rank_1["demand_category"] == "HIGH"
        assert float(sdr_rank_1["demand_score"]) >= 30.0

        # 4. Build Daily System Summary
        count_dsys = build_daily_system_summary(target_date, batch_id, run_id)
        assert count_dsys == 1

        dsys = fetch_one(
            "SELECT * FROM mart.daily_system_summary WHERE summary_date = CAST(:target_date AS DATE)",
            {"target_date": target_date},
        )
        assert dsys is not None
        assert dsys["station_count"] == 2
        assert dsys["region_count"] == 1

        # 5. Run DQ Checks
        run_daily_mart_dq_checks(run_id, batch_id, target_date)

    finally:
        pass
