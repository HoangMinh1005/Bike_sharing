import hashlib
import json
from datetime import datetime
from typing import Any, Dict

from src.common.db import execute_sql
from src.common.logger import get_logger
from src.common.time_utils import utc_now

logger = get_logger(__name__)


def compute_weather_hash(record: Dict[str, Any]) -> str:
    """
    Compute SHA256 hash of an individual hourly weather data dictionary.
    """
    serialized = json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def load_weather_raw(
    payload: Dict[str, Any],
    batch_id: str,
    run_id: str,
    location_name: str,
    latitude: float,
    longitude: float
) -> int:
    """
    Ingest Open-Meteo hourly weather payload.
    Normalizes arrays into individual hourly raw records and loads them into raw.weather_hourly.

    Returns the number of successfully loaded raw records.
    Raises ValueError if payload format is invalid.
    """
    logger.info(
        f"Loading raw weather hourly forecast. "
        f"batch_id={batch_id}, location={location_name}"
    )

    if not isinstance(payload, dict):
        raise ValueError("Invalid weather payload: payload must be a dictionary")

    hourly = payload.get("hourly")
    if not isinstance(hourly, dict) or "time" not in hourly:
        raise ValueError("Invalid weather payload: missing or invalid 'hourly' or 'time' object")

    times = hourly["time"]
    if not isinstance(times, list):
        raise ValueError("Invalid weather payload: 'time' field is not a list")

    # Extract metrics arrays
    temps = hourly.get("temperature_2m") or []
    humidities = hourly.get("relative_humidity_2m") or []
    precips = hourly.get("precipitation") or []
    wind_speeds = hourly.get("wind_speed_10m") or []
    weather_codes = hourly.get("weather_code") or []

    fetched_at = utc_now()

    insert_sql = """
        INSERT INTO raw.weather_hourly (
            batch_id,
            run_id,
            source_name,
            location_name,
            latitude,
            longitude,
            weather_time,
            fetched_at,
            raw_weather,
            payload_hash
        ) VALUES (
            :batch_id,
            :run_id,
            :source_name,
            :location_name,
            :latitude,
            :longitude,
            :weather_time,
            :fetched_at,
            CAST(:raw_weather AS JSONB),
            :payload_hash
        )
        ON CONFLICT (batch_id, location_name, weather_time) DO UPDATE SET
            raw_weather = EXCLUDED.raw_weather,
            payload_hash = EXCLUDED.payload_hash,
            run_id = EXCLUDED.run_id,
            fetched_at = EXCLUDED.fetched_at,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude
    """

    loaded_count = 0

    for i, time_str in enumerate(times):
        if not time_str:
            continue

        try:
            # Open-Meteo returns time in ISO format YYYY-MM-DDTHH:MM (e.g. 2026-07-21T10:00)
            weather_time = datetime.fromisoformat(time_str)
        except ValueError as e:
            logger.warning(f"Skipping record with invalid time string '{time_str}': {e}")
            continue

        # Extract values for this specific hour, handle index bounds safely
        t = temps[i] if i < len(temps) else None
        h = humidities[i] if i < len(humidities) else None
        p = precips[i] if i < len(precips) else None
        w = wind_speeds[i] if i < len(wind_speeds) else None
        c = weather_codes[i] if i < len(weather_codes) else None

        raw_weather_dict = {
            "temperature_2m": t,
            "relative_humidity_2m": h,
            "precipitation": p,
            "wind_speed_10m": w,
            "weather_code": c
        }

        payload_hash = compute_weather_hash(raw_weather_dict)
        raw_weather_json = json.dumps(raw_weather_dict, ensure_ascii=False)

        params = {
            "batch_id": batch_id,
            "run_id": run_id,
            "source_name": "open_meteo",
            "location_name": location_name,
            "latitude": latitude,
            "longitude": longitude,
            "weather_time": weather_time,
            "fetched_at": fetched_at,
            "raw_weather": raw_weather_json,
            "payload_hash": payload_hash
        }

        try:
            execute_sql(insert_sql, params)
            loaded_count += 1
        except Exception as e:
            logger.error(
                f"Failed to load weather record for location_name={location_name}, "
                f"time={time_str}: {e}"
            )
            # Weather API load failures are critical for the batch
            raise

    logger.info(
        f"Raw weather loading completed. "
        f"loaded_or_upserted={loaded_count} hourly record(s)"
    )

    return loaded_count
