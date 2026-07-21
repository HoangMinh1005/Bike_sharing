import uuid
import pytest

from src.common.config import get_settings
from src.common.db import execute_sql, fetch_one, fetch_all
from src.extract.weather_client import WeatherClient
from src.load.weather_raw_loader import load_weather_raw
from src.load.calendar_raw_loader import load_calendar_raw
from src.transform.weather_transformer import transform_weather_hourly
from src.transform.calendar_transformer import transform_calendar
from src.quality.weather_calendar_checks import run_weather_calendar_dq_checks


@pytest.fixture
def clean_test_batches():
    batches = []
    yield batches
    for batch_id in batches:
        execute_sql("DELETE FROM staging.weather_hourly WHERE batch_id = :batch_id", {"batch_id": batch_id})
        execute_sql("DELETE FROM staging.calendar WHERE batch_id = :batch_id", {"batch_id": batch_id})
        execute_sql("DELETE FROM raw.weather_hourly WHERE batch_id = :batch_id", {"batch_id": batch_id})
        execute_sql("DELETE FROM raw.calendar WHERE batch_id = :batch_id", {"batch_id": batch_id})
        execute_sql("DELETE FROM etl_metadata.dq_results WHERE run_id = :batch_id", {"batch_id": batch_id})
        execute_sql("DELETE FROM etl_metadata.rejected_records WHERE run_id = :batch_id", {"batch_id": batch_id})


def test_weather_client_response():
    """Unit test for weather client fetch parsing structure."""
    settings = get_settings()
    client = WeatherClient(settings.WEATHER_API_BASE_URL)
    payload = client.fetch_hourly_weather(
        latitude=40.7128,
        longitude=-74.0060,
        timezone="America/New_York",
        lookback_hours=12
    )
    assert "hourly" in payload
    assert "temperature_2m" in payload["hourly"]
    assert len(payload["hourly"]["time"]) > 0


def test_idempotent_weather_loader(clean_test_batches):
    """Verify raw weather loader conflict targets are updated rather than duplicated."""
    batch_id = f"test-weather-idemp-{uuid.uuid4()}"
    clean_test_batches.append(batch_id)
    
    mock_payload = {
        "hourly": {
            "time": ["2026-07-21T10:00", "2026-07-21T11:00"],
            "temperature_2m": [25.5, 26.2],
            "relative_humidity_2m": [60, 58],
            "precipitation": [0.0, 0.0],
            "wind_speed_10m": [12.4, 11.8],
            "weather_code": [0, 1]
        }
    }

    # Load first time
    c1 = load_weather_raw(
        payload=mock_payload,
        batch_id=batch_id,
        run_id=batch_id,
        location_name="test_loc",
        latitude=40.0,
        longitude=-70.0
    )
    assert c1 == 2

    # Load second time (same batch)
    c2 = load_weather_raw(
        payload=mock_payload,
        batch_id=batch_id,
        run_id=batch_id,
        location_name="test_loc",
        latitude=40.0,
        longitude=-70.0
    )
    assert c2 == 2

    # Query database to confirm count is still 2
    res = fetch_one(
        "SELECT COUNT(*) AS cnt FROM raw.weather_hourly WHERE batch_id = :batch_id",
        {"batch_id": batch_id}
    )
    assert res["cnt"] == 2


def test_calendar_loader_and_transformer(clean_test_batches, tmp_path):
    """Test calendar CSV parsing, loading, and transformations."""
    batch_id = f"test-cal-{uuid.uuid4()}"
    clean_test_batches.append(batch_id)

    # Write a temporary mock calendar CSV
    csv_file = tmp_path / "mock_calendar.csv"
    with open(csv_file, "w", encoding="utf-8") as f:
        f.write("date,day_of_week,is_weekend,is_holiday,holiday_name\n")
        f.write("2026-01-01,Thursday,false,true,New Year's Day\n")
        f.write("2026-01-03,Saturday,true,false,\n")

    # 1. Load raw
    loaded = load_calendar_raw(str(csv_file), batch_id, batch_id)
    assert loaded == 2

    # 2. Transform staging
    tx = transform_calendar(batch_id)
    assert tx == 2

    # 3. Verify values
    rows = fetch_all(
        "SELECT * FROM staging.calendar WHERE batch_id = :batch_id ORDER BY calendar_date",
        {"batch_id": batch_id}
    )
    assert len(rows) == 2
    assert rows[0]["calendar_date"].isoformat() == "2026-01-01"
    assert rows[0]["day_of_week"] == "Thursday"
    assert rows[0]["is_weekend"] is False
    assert rows[0]["is_holiday"] is True
    assert rows[0]["holiday_name"] == "New Year's Day"

    assert rows[1]["calendar_date"].isoformat() == "2026-01-03"
    assert rows[1]["is_weekend"] is True
    assert rows[1]["is_holiday"] is False
