import json
from typing import Any, Dict, Optional

from src.common.db import execute_sql, fetch_all
from src.common.logger import get_logger

logger = get_logger(__name__)


def _parse_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _parse_int(val: Any) -> Optional[int]:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _parse_raw_weather(raw_weather: Any) -> Optional[Dict[str, Any]]:
    if isinstance(raw_weather, dict):
        return raw_weather
    if isinstance(raw_weather, str):
        try:
            return json.loads(raw_weather)
        except Exception as e:
            logger.warning(f"Failed to parse raw_weather JSON string: {e}")
            return None
    return None


def transform_weather_hourly(batch_id: str) -> int:
    """
    Transform raw.weather_hourly records into staging.weather_hourly.
    Uses location_name + weather_time + batch_id as conflict target.

    Returns the number of records successfully transformed.
    """
    logger.info(f"Transforming weather_hourly to staging for batch={batch_id}")

    sql_select = """
        SELECT
            location_name,
            latitude,
            longitude,
            weather_time,
            fetched_at,
            raw_weather
        FROM raw.weather_hourly
        WHERE batch_id = :batch_id
    """

    rows = fetch_all(sql_select, {"batch_id": batch_id})
    if not rows:
        logger.warning(f"No raw weather records found for batch_id={batch_id}")
        return 0

    sql_upsert = """
        INSERT INTO staging.weather_hourly (
            location_name,
            latitude,
            longitude,
            weather_time,
            temperature,
            humidity,
            precipitation,
            wind_speed,
            weather_code,
            fetched_at,
            batch_id,
            updated_at
        ) VALUES (
            :location_name,
            :latitude,
            :longitude,
            :weather_time,
            :temperature,
            :humidity,
            :precipitation,
            :wind_speed,
            :weather_code,
            :fetched_at,
            :batch_id,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (location_name, weather_time, batch_id) DO UPDATE SET
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            temperature = EXCLUDED.temperature,
            humidity = EXCLUDED.humidity,
            precipitation = EXCLUDED.precipitation,
            wind_speed = EXCLUDED.wind_speed,
            weather_code = EXCLUDED.weather_code,
            fetched_at = EXCLUDED.fetched_at,
            updated_at = CURRENT_TIMESTAMP
    """

    processed = 0

    for row in rows:
        location_name = row["location_name"]
        weather_time = row["weather_time"]
        fetched_at = row["fetched_at"]
        raw_weather_val = row["raw_weather"]

        raw_weather = _parse_raw_weather(raw_weather_val)
        if raw_weather is None:
            logger.warning(
                f"Skipping weather record for location={location_name}, "
                f"time={weather_time} due to empty/unparseable raw_weather payload."
            )
            continue

        params = {
            "location_name": location_name,
            "latitude": float(row["latitude"]),
            "longitude": float(row["longitude"]),
            "weather_time": weather_time,
            "temperature": _parse_float(raw_weather.get("temperature_2m")),
            "humidity": _parse_float(raw_weather.get("relative_humidity_2m")),
            "precipitation": _parse_float(raw_weather.get("precipitation")),
            "wind_speed": _parse_float(raw_weather.get("wind_speed_10m")),
            "weather_code": _parse_int(raw_weather.get("weather_code")),
            "fetched_at": fetched_at,
            "batch_id": batch_id,
        }

        try:
            execute_sql(sql_upsert, params)
            processed += 1
        except Exception as e:
            logger.error(
                f"Failed to transform weather record for location={location_name}, "
                f"time={weather_time}: {e}"
            )
            raise

    logger.info(
        f"Transformed weather_hourly to staging: "
        f"processed={processed} record(s)"
    )

    return processed
