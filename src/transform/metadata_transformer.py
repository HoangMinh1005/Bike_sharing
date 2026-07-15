import json
from typing import Any, Dict, List, Optional

from src.common.db import execute_sql, fetch_all, fetch_one
from src.common.logger import get_logger

logger = get_logger(__name__)


def _get_raw_payload(batch_id: str, feed_name: str) -> Dict[str, Any]:
    """
    Fetch the latest raw payload for a specific feed in a batch.

    Raises:
        ValueError: if the payload does not exist, cannot be parsed,
                    or is not a JSON object.
    """
    sql = """
        SELECT raw_payload
        FROM raw.gbfs_feed_snapshots
        WHERE batch_id = :batch_id
          AND feed_name = :feed_name
        ORDER BY fetched_at DESC
        LIMIT 1
    """

    row = fetch_one(
        sql,
        {
            "batch_id": batch_id,
            "feed_name": feed_name,
        },
    )

    if not row:
        raise ValueError(
            f"No raw payload found for feed '{feed_name}' in batch '{batch_id}'"
        )

    payload = row["raw_payload"]

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except ValueError as e:
            raise ValueError(
                f"Failed to parse raw_payload as JSON for feed '{feed_name}': {e}"
            ) from e

    if not isinstance(payload, dict):
        raise ValueError(
            f"raw_payload for feed '{feed_name}' must be a JSON object"
        )

    return payload


def _get_required_data_object(payload: Dict[str, Any], feed_name: str) -> Dict[str, Any]:
    """
    Return payload['data'] and ensure it is a dictionary.
    """
    data = payload.get("data")

    if not isinstance(data, dict):
        raise ValueError(
            f"Invalid payload for feed '{feed_name}': missing or invalid 'data' object"
        )

    return data


def _get_required_list(
    data: Dict[str, Any],
    feed_name: str,
    list_key: str,
) -> List[Dict[str, Any]]:
    """
    Return a required list from payload['data'].
    """
    value = data.get(list_key)

    if not isinstance(value, list):
        raise ValueError(
            f"Invalid payload for feed '{feed_name}': missing or invalid '{list_key}' list"
        )

    return value


def transform_system_information(batch_id: str) -> int:
    """
    Transform raw system_information payload into staging.system_information.

    Required by schema:
    - system_id

    Optional:
    - system_name
    - operator
    - timezone
    - url
    """
    payload = _get_raw_payload(batch_id, "system_information")
    data = _get_required_data_object(payload, "system_information")

    system_id = data.get("system_id")

    if not system_id:
        raise ValueError(
            f"system_information payload in batch '{batch_id}' is missing required field 'system_id'"
        )

    sql = """
        INSERT INTO staging.system_information (
            system_id,
            system_name,
            operator,
            timezone,
            url,
            loaded_at
        ) VALUES (
            :system_id,
            :system_name,
            :operator,
            :timezone,
            :url,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (system_id) DO UPDATE SET
            system_name = EXCLUDED.system_name,
            operator = EXCLUDED.operator,
            timezone = EXCLUDED.timezone,
            url = EXCLUDED.url,
            loaded_at = EXCLUDED.loaded_at
    """

    params = {
        "system_id": system_id,
        "system_name": data.get("name"),
        "operator": data.get("operator"),
        "timezone": data.get("timezone"),
        "url": data.get("url"),
    }

    row_count = execute_sql(sql, params)

    logger.info(
        f"Transformed system_information for batch '{batch_id}': processed {row_count} record(s)"
    )

    return row_count


def transform_regions(batch_id: str) -> int:
    """
    Transform raw system_regions payload into staging.regions.

    Required by schema:
    - region_id
    - region_name
    """
    payload = _get_raw_payload(batch_id, "system_regions")
    data = _get_required_data_object(payload, "system_regions")
    regions = _get_required_list(data, "system_regions", "regions")

    sql = """
        INSERT INTO staging.regions (
            region_id,
            region_name,
            loaded_at
        ) VALUES (
            :region_id,
            :region_name,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (region_id) DO UPDATE SET
            region_name = EXCLUDED.region_name,
            loaded_at = EXCLUDED.loaded_at
    """

    processed = 0
    skipped = 0

    for region in regions:
        region_id = region.get("region_id")
        region_name = region.get("name")

        if not region_id or not region_name:
            skipped += 1
            logger.warning(
                f"Skipping invalid region record: missing region_id or name. record={region}"
            )
            continue

        params = {
            "region_id": region_id,
            "region_name": region_name,
        }

        execute_sql(sql, params)
        processed += 1

    logger.info(
        f"Transformed system_regions for batch '{batch_id}': processed={processed}, skipped={skipped}"
    )

    if processed == 0:
        raise ValueError(
            f"No valid regions were transformed for batch '{batch_id}'"
        )

    return processed


def transform_vehicle_types(batch_id: str) -> int:
    """
    Transform raw vehicle_types payload into staging.vehicle_types.

    Required by schema:
    - vehicle_type_id

    Optional:
    - vehicle_type_name
    - form_factor
    - propulsion_type
    - max_range_meters
    """
    payload = _get_raw_payload(batch_id, "vehicle_types")
    data = _get_required_data_object(payload, "vehicle_types")
    vehicle_types = _get_required_list(data, "vehicle_types", "vehicle_types")

    sql = """
        INSERT INTO staging.vehicle_types (
            vehicle_type_id,
            vehicle_type_name,
            form_factor,
            propulsion_type,
            max_range_meters,
            loaded_at
        ) VALUES (
            :vehicle_type_id,
            :vehicle_type_name,
            :form_factor,
            :propulsion_type,
            :max_range_meters,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (vehicle_type_id) DO UPDATE SET
            vehicle_type_name = EXCLUDED.vehicle_type_name,
            form_factor = EXCLUDED.form_factor,
            propulsion_type = EXCLUDED.propulsion_type,
            max_range_meters = EXCLUDED.max_range_meters,
            loaded_at = EXCLUDED.loaded_at
    """

    processed = 0
    skipped = 0

    for vehicle_type in vehicle_types:
        vehicle_type_id = vehicle_type.get("vehicle_type_id")

        if not vehicle_type_id:
            skipped += 1
            logger.warning(
                f"Skipping invalid vehicle_type record: missing vehicle_type_id. record={vehicle_type}"
            )
            continue

        params = {
            "vehicle_type_id": vehicle_type_id,
            "vehicle_type_name": vehicle_type.get("name"),
            "form_factor": vehicle_type.get("form_factor"),
            "propulsion_type": vehicle_type.get("propulsion_type"),
            "max_range_meters": vehicle_type.get("max_range_meters"),
        }

        execute_sql(sql, params)
        processed += 1

    logger.info(
        f"Transformed vehicle_types for batch '{batch_id}': processed={processed}, skipped={skipped}"
    )

    if processed == 0:
        raise ValueError(
            f"No valid vehicle types were transformed for batch '{batch_id}'"
        )

    return processed


def transform_stations(batch_id: str) -> int:
    """
    Transform raw station_information payload into staging.stations.

    Required by schema:
    - station_id
    - station_name

    Optional:
    - short_name
    - latitude
    - longitude
    - region_id
    - capacity
    - is_active

    Note:
    - staging.stations.region_id has a foreign key to staging.regions(region_id).
    - If region_id from source does not exist in staging.regions, it will be set to NULL.
    """
    payload = _get_raw_payload(batch_id, "station_information")
    data = _get_required_data_object(payload, "station_information")
    stations = _get_required_list(data, "station_information", "stations")

    existing_regions = fetch_all(
        """
        SELECT region_id
        FROM staging.regions
        """
    )

    existing_region_ids = {
        row["region_id"]
        for row in existing_regions
        if row.get("region_id") is not None
    }

    sql = """
        INSERT INTO staging.stations (
            station_id,
            station_name,
            short_name,
            latitude,
            longitude,
            region_id,
            capacity,
            is_active,
            loaded_at
        ) VALUES (
            :station_id,
            :station_name,
            :short_name,
            :latitude,
            :longitude,
            :region_id,
            :capacity,
            :is_active,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (station_id) DO UPDATE SET
            station_name = EXCLUDED.station_name,
            short_name = EXCLUDED.short_name,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            region_id = EXCLUDED.region_id,
            capacity = EXCLUDED.capacity,
            is_active = EXCLUDED.is_active,
            loaded_at = EXCLUDED.loaded_at
    """

    processed = 0
    skipped = 0
    region_null_count = 0

    for station in stations:
        station_id = station.get("station_id")
        station_name = station.get("name")

        if not station_id or not station_name:
            skipped += 1
            logger.warning(
                f"Skipping invalid station record: missing station_id or name. record={station}"
            )
            continue

        region_id = station.get("region_id")

        if region_id and region_id not in existing_region_ids:
            logger.warning(
                f"Station '{station_id}' has unknown region_id='{region_id}'. Setting region_id to NULL."
            )
            region_id = None
            region_null_count += 1

        params = {
            "station_id": station_id,
            "station_name": station_name,
            "short_name": station.get("short_name"),
            "latitude": station.get("lat"),
            "longitude": station.get("lon"),
            "region_id": region_id,
            "capacity": station.get("capacity"),
            "is_active": True,
        }

        execute_sql(sql, params)
        processed += 1

    logger.info(
        f"Transformed station_information for batch '{batch_id}': "
        f"processed={processed}, skipped={skipped}, region_set_null={region_null_count}"
    )

    if processed == 0:
        raise ValueError(
            f"No valid stations were transformed for batch '{batch_id}'"
        )

    return processed