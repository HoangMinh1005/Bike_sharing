import json
from typing import Any, Dict, Optional

from src.common.db import execute_sql, fetch_all
from src.common.logger import get_logger
from src.common.time_utils import safe_timestamp_from_gbfs

logger = get_logger(__name__)


def _parse_bool(val: Any, default: bool = True) -> bool:
    """
    Parse boolean values from GBFS JSON safely.
    GBFS may return boolean fields as true/false, 1/0, or string values.
    """
    if val is None:
        return default

    if isinstance(val, bool):
        return val

    if isinstance(val, int):
        return val != 0

    if isinstance(val, str):
        normalized = val.strip().lower()

        if normalized in ("true", "1", "yes"):
            return True

        if normalized in ("false", "0", "no"):
            return False

    return default


def _parse_int(
    val: Any,
    default: int = 0,
    field_name: str = "",
    station_id: str = "",
) -> int:
    """
    Parse integer values safely.

    Invalid numeric values are converted to default and logged.
    Negative values are not changed here because DQ checks should detect them.
    """
    if val is None:
        return default

    try:
        return int(val)
    except (TypeError, ValueError):
        logger.warning(
            f"Invalid integer value. "
            f"station_id={station_id}, field={field_name}, value={val}. "
            f"Using default={default}"
        )
        return default


def _parse_raw_station(raw_station_status: Any, station_id: str) -> Optional[Dict[str, Any]]:
    """
    Parse raw_station_status from PostgreSQL JSONB or string format.
    """
    if isinstance(raw_station_status, dict):
        return raw_station_status

    if isinstance(raw_station_status, str):
        try:
            return json.loads(raw_station_status)
        except Exception as e:
            logger.warning(
                f"Failed to parse raw_station_status JSON string. "
                f"station_id={station_id}, error={e}"
            )
            return None

    logger.warning(
        f"raw_station_status has unsupported type. "
        f"station_id={station_id}, type={type(raw_station_status)}"
    )

    return None


def transform_station_status(batch_id: str) -> int:
    """
    Transform raw station_status snapshots into staging.station_status.

    Important:
    - station_status is dynamic time-series data.
    - Therefore staging.station_status must keep historical snapshots.
    - The UPSERT key should be (station_id, batch_id), not only station_id.

    Returns:
        Number of processed station_status records.
    """
    logger.info(f"Transforming station_status to staging for batch_id={batch_id}")

    sql_select = """
        SELECT
            fetched_at,
            source_last_updated,
            station_id,
            raw_station_status
        FROM raw.station_status_snapshots
        WHERE batch_id = :batch_id
    """

    rows = fetch_all(sql_select, {"batch_id": batch_id})

    if not rows:
        logger.warning(
            f"No raw station_status records found for batch_id={batch_id}"
        )
        return 0

    sql_upsert = """
        INSERT INTO staging.station_status (
            station_id,
            num_bikes_available,
            num_docks_available,
            num_bikes_disabled,
            num_docks_disabled,
            is_installed,
            is_renting,
            is_returning,
            last_reported,
            source_last_updated,
            fetched_at,
            batch_id,
            updated_at
        ) VALUES (
            :station_id,
            :num_bikes_available,
            :num_docks_available,
            :num_bikes_disabled,
            :num_docks_disabled,
            :is_installed,
            :is_renting,
            :is_returning,
            :last_reported,
            :source_last_updated,
            :fetched_at,
            :batch_id,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (station_id, batch_id) DO UPDATE SET
            num_bikes_available = EXCLUDED.num_bikes_available,
            num_docks_available = EXCLUDED.num_docks_available,
            num_bikes_disabled = EXCLUDED.num_bikes_disabled,
            num_docks_disabled = EXCLUDED.num_docks_disabled,
            is_installed = EXCLUDED.is_installed,
            is_renting = EXCLUDED.is_renting,
            is_returning = EXCLUDED.is_returning,
            last_reported = EXCLUDED.last_reported,
            source_last_updated = EXCLUDED.source_last_updated,
            fetched_at = EXCLUDED.fetched_at,
            updated_at = CURRENT_TIMESTAMP
    """

    processed = 0
    skipped = 0

    for row in rows:
        station_id = str(row["station_id"]).strip()
        fetched_at = row["fetched_at"]
        source_last_updated = row["source_last_updated"]
        raw_station_status = row["raw_station_status"]

        raw_station = _parse_raw_station(raw_station_status, station_id)

        if raw_station is None:
            skipped += 1
            continue

        last_reported = safe_timestamp_from_gbfs(raw_station.get("last_reported"))

        if last_reported is None:
            last_reported = source_last_updated

        params = {
            "station_id": station_id,
            "num_bikes_available": _parse_int(
                raw_station.get("num_bikes_available"),
                field_name="num_bikes_available",
                station_id=station_id,
            ),
            "num_docks_available": _parse_int(
                raw_station.get("num_docks_available"),
                field_name="num_docks_available",
                station_id=station_id,
            ),
            "num_bikes_disabled": _parse_int(
                raw_station.get("num_bikes_disabled"),
                field_name="num_bikes_disabled",
                station_id=station_id,
            ),
            "num_docks_disabled": _parse_int(
                raw_station.get("num_docks_disabled"),
                field_name="num_docks_disabled",
                station_id=station_id,
            ),
            "is_installed": _parse_bool(raw_station.get("is_installed"), True),
            "is_renting": _parse_bool(raw_station.get("is_renting"), True),
            "is_returning": _parse_bool(raw_station.get("is_returning"), True),
            "last_reported": last_reported,
            "source_last_updated": source_last_updated,
            "fetched_at": fetched_at,
            "batch_id": batch_id,
        }

        try:
            execute_sql(sql_upsert, params)
            processed += 1
        except Exception as e:
            logger.error(
                f"Failed to transform station_status record. "
                f"station_id={station_id}, batch_id={batch_id}, error={e}"
            )
            skipped += 1

    logger.info(
        f"Transformed station_status for batch_id={batch_id}. "
        f"processed={processed}, skipped={skipped}"
    )

    return processed


def transform_station_vehicle_type_status(batch_id: str) -> int:
    """
    Transform nested vehicle_types_available from raw station_status snapshots
    into staging.station_vehicle_type_status.

    Important:
    - vehicle type availability is also snapshot-based.
    - The UPSERT key should be (station_id, vehicle_type_id, batch_id).
    - This keeps historical vehicle type availability per station per snapshot.

    Returns:
        Number of processed vehicle type records.
    """
    logger.info(
        f"Transforming nested vehicle_types_available for batch_id={batch_id}"
    )

    sql_select = """
        SELECT
            station_id,
            fetched_at,
            source_last_updated,
            raw_station_status
        FROM raw.station_status_snapshots
        WHERE batch_id = :batch_id
    """

    rows = fetch_all(sql_select, {"batch_id": batch_id})

    if not rows:
        logger.warning(
            f"No raw station_status records found for vehicle type transform. "
            f"batch_id={batch_id}"
        )
        return 0

    sql_upsert = """
        INSERT INTO staging.station_vehicle_type_status (
            station_id,
            vehicle_type_id,
            count,
            last_reported,
            source_last_updated,
            fetched_at,
            batch_id,
            loaded_at
        ) VALUES (
            :station_id,
            :vehicle_type_id,
            :count,
            :last_reported,
            :source_last_updated,
            :fetched_at,
            :batch_id,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (station_id, vehicle_type_id, batch_id) DO UPDATE SET
            count = EXCLUDED.count,
            last_reported = EXCLUDED.last_reported,
            source_last_updated = EXCLUDED.source_last_updated,
            fetched_at = EXCLUDED.fetched_at,
            loaded_at = CURRENT_TIMESTAMP
    """

    processed = 0
    skipped = 0

    for row in rows:
        station_id = str(row["station_id"]).strip()
        fetched_at = row["fetched_at"]
        source_last_updated = row["source_last_updated"]
        raw_station_status = row["raw_station_status"]

        raw_station = _parse_raw_station(raw_station_status, station_id)

        if raw_station is None:
            skipped += 1
            continue

        vehicle_types = raw_station.get("vehicle_types_available")

        if vehicle_types is None:
            continue

        if not isinstance(vehicle_types, list):
            logger.warning(
                f"vehicle_types_available is not a list. "
                f"station_id={station_id}, batch_id={batch_id}"
            )
            skipped += 1
            continue

        last_reported = safe_timestamp_from_gbfs(raw_station.get("last_reported"))

        if last_reported is None:
            last_reported = source_last_updated

        for vehicle_type in vehicle_types:
            if not isinstance(vehicle_type, dict):
                logger.warning(
                    f"Skipping invalid vehicle type record. "
                    f"station_id={station_id}, value={vehicle_type}"
                )
                skipped += 1
                continue

            vehicle_type_id = vehicle_type.get("vehicle_type_id")
            count = vehicle_type.get("count")

            if vehicle_type_id is None or str(vehicle_type_id).strip() == "":
                logger.warning(
                    f"Skipping vehicle type record without vehicle_type_id. "
                    f"station_id={station_id}, record={vehicle_type}"
                )
                skipped += 1
                continue

            if count is None:
                logger.warning(
                    f"Skipping vehicle type record without count. "
                    f"station_id={station_id}, vehicle_type_id={vehicle_type_id}"
                )
                skipped += 1
                continue

            vehicle_type_id = str(vehicle_type_id).strip()

            params = {
                "station_id": station_id,
                "vehicle_type_id": vehicle_type_id,
                "count": _parse_int(
                    count,
                    field_name="vehicle_type_count",
                    station_id=station_id,
                ),
                "last_reported": last_reported,
                "source_last_updated": source_last_updated,
                "fetched_at": fetched_at,
                "batch_id": batch_id,
            }

            try:
                execute_sql(sql_upsert, params)
                processed += 1
            except Exception as e:
                logger.error(
                    f"Failed to transform vehicle type status. "
                    f"station_id={station_id}, "
                    f"vehicle_type_id={vehicle_type_id}, "
                    f"batch_id={batch_id}, error={e}"
                )
                skipped += 1

    logger.info(
        f"Transformed vehicle_types_available for batch_id={batch_id}. "
        f"processed={processed}, skipped={skipped}"
    )

    return processed