import uuid
import pytest
import pendulum

from src.common.db import execute_sql, fetch_one, fetch_all
from src.mart.hourly_mart_builder import (
    build_hourly_station_availability,
    build_hourly_region_availability,
    build_vehicle_type_availability_summary,
    build_weather_mobility_summary,
)
from src.quality.hourly_mart_checks import run_hourly_mart_dq_checks


@pytest.fixture
def clean_test_windows():
    windows = []
    yield windows
    for start, end in windows:
        params = {"start": start, "end": end}
        execute_sql("DELETE FROM mart.weather_mobility_summary WHERE hour_bucket >= CAST(:start AS TIMESTAMP) AND hour_bucket < CAST(:end AS TIMESTAMP)", params)
        execute_sql("DELETE FROM mart.vehicle_type_availability_summary WHERE hour_bucket >= CAST(:start AS TIMESTAMP) AND hour_bucket < CAST(:end AS TIMESTAMP)", params)
        execute_sql("DELETE FROM mart.hourly_region_availability WHERE hour_bucket >= CAST(:start AS TIMESTAMP) AND hour_bucket < CAST(:end AS TIMESTAMP)", params)
        execute_sql("DELETE FROM mart.hourly_station_availability WHERE hour_bucket >= CAST(:start AS TIMESTAMP) AND hour_bucket < CAST(:end AS TIMESTAMP)", params)


def test_hourly_mart_builder_invalid_window():
    """Verify that invalid target hour windows raise ValueError."""
    start = "2026-07-22T10:00:00"
    end = "2026-07-22T09:00:00"
    batch_id = f"test-invalid-{uuid.uuid4()}"

    with pytest.raises(ValueError):
        build_hourly_station_availability(start, end, batch_id, batch_id)

    with pytest.raises(ValueError):
        build_hourly_region_availability(start, end, batch_id, batch_id)

    with pytest.raises(ValueError):
        build_vehicle_type_availability_summary(start, end, batch_id, batch_id)

    with pytest.raises(ValueError):
        build_weather_mobility_summary(start, end, batch_id, batch_id)


def test_hourly_mart_builder_end_to_end_flow(clean_test_windows):
    """Test full mart building flow with mock staging data."""
    batch_id = f"test-mart-{uuid.uuid4()}"
    run_id = batch_id

    target_start = "2026-07-22T08:00:00"
    target_end = "2026-07-22T09:00:00"
    clean_test_windows.append((target_start, target_end))

    params = {"batch_id": batch_id}

    try:
        # Insert mock staging region
        execute_sql(
            """
            INSERT INTO staging.regions (region_id, region_name, source_batch_id)
            VALUES ('reg-test-01', 'Test Region 01', :batch_id)
            ON CONFLICT (region_id) DO NOTHING
            """,
            params,
        )

        # Insert mock staging station
        execute_sql(
            """
            INSERT INTO staging.stations (station_id, station_name, region_id, capacity, source_batch_id)
            VALUES ('st-test-01', 'Test Station 01', 'reg-test-01', 20, :batch_id)
            ON CONFLICT (station_id) DO NOTHING
            """,
            params,
        )

        # Insert mock staging station status
        execute_sql(
            """
            INSERT INTO staging.station_status (
                station_id, num_bikes_available, num_docks_available, num_bikes_disabled,
                num_docks_disabled, is_installed, is_renting, is_returning,
                last_reported, source_last_updated, fetched_at, batch_id
            ) VALUES (
                'st-test-01', 10, 10, 0, 0, true, true, true,
                '2026-07-22T08:15:00', '2026-07-22T08:15:00', '2026-07-22T08:15:00', :batch_id
            )
            ON CONFLICT (station_id, batch_id) DO NOTHING
            """,
            params,
        )

        # Insert mock staging weather
        execute_sql(
            """
            INSERT INTO staging.weather_hourly (
                location_name, latitude, longitude, weather_time, temperature, humidity,
                precipitation, wind_speed, weather_code, fetched_at, batch_id
            ) VALUES (
                'brooklyn', 40.6782, -73.9442, '2026-07-22T08:00:00', 22.5, 55.0,
                0.0, 10.2, 0, '2026-07-22T08:00:00', :batch_id
            )
            ON CONFLICT (location_name, weather_time, batch_id) DO NOTHING
            """,
            params,
        )

        # Insert mock staging calendar
        execute_sql(
            """
            INSERT INTO staging.calendar (
                calendar_date, day_of_week, is_weekend, is_holiday, batch_id
            ) VALUES (
                '2026-07-22', 'Wednesday', false, false, :batch_id
            )
            ON CONFLICT (calendar_date, batch_id) DO NOTHING
            """,
            params,
        )

        # 1. Build station availability mart
        c1 = build_hourly_station_availability(target_start, target_end, batch_id, run_id)
        assert c1 >= 1

        # 2. Build region availability mart
        c2 = build_hourly_region_availability(target_start, target_end, batch_id, run_id)
        assert c2 >= 1

        # 3. Build weather mobility summary mart
        c4 = build_weather_mobility_summary(target_start, target_end, batch_id, run_id)
        assert c4 == 1

        # Verify idempotency by calling builders a second time
        c1_rerun = build_hourly_station_availability(target_start, target_end, batch_id, run_id)
        assert c1_rerun == c1

        # Run DQ checks
        run_hourly_mart_dq_checks(run_id, batch_id, target_start, target_end)

        # Query database to confirm non-empty metrics
        row_station = fetch_one(
            """
            SELECT * FROM mart.hourly_station_availability
            WHERE hour_bucket = CAST(:target_start AS TIMESTAMP) AND station_id = 'st-test-01'
            """,
            {"target_start": target_start},
        )
        assert row_station is not None
        assert row_station["avg_bikes_available"] == 10
        assert row_station["capacity"] == 20
        assert float(row_station["availability_rate"]) == 0.5

    finally:
        # Clean up staging mock test records
        execute_sql("DELETE FROM staging.station_status WHERE batch_id = :batch_id", params)
        execute_sql("DELETE FROM staging.weather_hourly WHERE batch_id = :batch_id", params)
        execute_sql("DELETE FROM staging.calendar WHERE batch_id = :batch_id", params)
