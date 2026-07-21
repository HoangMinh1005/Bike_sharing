import hashlib
import json
from typing import Any, Dict

from src.common.db import execute_sql
from src.common.logger import get_logger
from src.common.time_utils import safe_timestamp_from_gbfs, utc_now

logger = get_logger(__name__)


def compute_station_hash(station: Dict[str, Any]) -> str:
    """
    Compute SHA256 hash of an individual station status JSON object.

    The JSON is serialized with sorted keys so the same station object
    always produces the same hash even if key order changes.
    """
    serialized = json.dumps(
        station,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def load_station_status_raw(
    payload: Dict[str, Any],
    batch_id: str,
    run_id: str,
    language: str = "en",
) -> int:
    """
    Ingest a GBFS station_status feed payload.

    This function splits the station_status feed into one raw record per station
    and loads the result into raw.station_status_snapshots.

    Returns:
        Number of station records inserted or upserted successfully.

    Raises:
        ValueError: If the payload structure is invalid.
        RuntimeError: If input has station records but none can be loaded.
    """
    logger.info(
        f"Loading raw station status snapshots. "
        f"batch_id={batch_id}, run_id={run_id}"
    )

    if not isinstance(payload, dict):
        raise ValueError(
            "Invalid GBFS station_status payload: payload must be a dictionary"
        )

    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError(
            "Invalid GBFS station_status payload: missing or invalid 'data' object"
        )

    stations = data.get("stations")
    if not isinstance(stations, list):
        raise ValueError(
            "Invalid GBFS station_status payload: missing or invalid 'stations' list"
        )

    if len(stations) == 0:
        raise ValueError(
            "Invalid GBFS station_status payload: stations list is empty"
        )

    fetched_at = utc_now()

    ttl = payload.get("ttl")

    source_last_updated = safe_timestamp_from_gbfs(payload.get("last_updated"))
    if source_last_updated is None:
        source_last_updated = fetched_at

    insert_sql = """
        INSERT INTO raw.station_status_snapshots (
            batch_id,
            run_id,
            feed_name,
            language,
            fetched_at,
            source_last_updated,
            ttl,
            station_id,
            raw_station_status,
            payload_hash
        ) VALUES (
            :batch_id,
            :run_id,
            :feed_name,
            :language,
            :fetched_at,
            :source_last_updated,
            :ttl,
            :station_id,
            CAST(:raw_station_status AS JSONB),
            :payload_hash
        )
        ON CONFLICT (batch_id, station_id, source_last_updated) DO UPDATE SET
            raw_station_status = EXCLUDED.raw_station_status,
            payload_hash = EXCLUDED.payload_hash,
            run_id = EXCLUDED.run_id,
            fetched_at = EXCLUDED.fetched_at,
            ttl = EXCLUDED.ttl
    """

    reject_sql = """
        INSERT INTO etl_metadata.rejected_records (
            run_id,
            source_name,
            table_name,
            reason,
            raw_payload
        ) VALUES (
            :run_id,
            :source_name,
            :table_name,
            :reason,
            CAST(:raw_payload AS JSONB)
        )
    """

    loaded_count = 0
    rejected_count = 0

    for station in stations:
        if not isinstance(station, dict):
            logger.warning(f"Skipping non-dictionary station record: {station}")

            try:
                execute_sql(
                    reject_sql,
                    {
                        "run_id": run_id,
                        "source_name": "gbfs_station_status",
                        "table_name": "raw.station_status_snapshots",
                        "reason": "Station record is not a JSON object",
                        "raw_payload": json.dumps(
                            {"invalid_record": station},
                            ensure_ascii=False,
                        ),
                    },
                )
                rejected_count += 1
            except Exception as e:
                logger.error(f"Failed to log rejected non-dict record: {e}")

            continue

        station_id = station.get("station_id")

        if station_id is None or str(station_id).strip() == "":
            logger.warning(
                f"Station record is missing required 'station_id'. "
                f"record={station}"
            )

            try:
                execute_sql(
                    reject_sql,
                    {
                        "run_id": run_id,
                        "source_name": "gbfs_station_status",
                        "table_name": "raw.station_status_snapshots",
                        "reason": "Missing required field station_id",
                        "raw_payload": json.dumps(station, ensure_ascii=False),
                    },
                )
                rejected_count += 1
            except Exception as e:
                logger.error(f"Failed to log rejected record to database: {e}")

            continue

        station_id = str(station_id).strip()

        try:
            payload_hash = compute_station_hash(station)
            station_json = json.dumps(station, ensure_ascii=False)

            params = {
                "batch_id": batch_id,
                "run_id": run_id,
                "feed_name": "station_status",
                "language": language,
                "fetched_at": fetched_at,
                "source_last_updated": source_last_updated,
                "ttl": ttl,
                "station_id": station_id,
                "raw_station_status": station_json,
                "payload_hash": payload_hash,
            }

            execute_sql(insert_sql, params)
            loaded_count += 1

        except Exception as e:
            logger.error(
                f"Failed to load raw station status for "
                f"station_id={station_id}: {e}"
            )

            try:
                execute_sql(
                    reject_sql,
                    {
                        "run_id": run_id,
                        "source_name": "gbfs_station_status",
                        "table_name": "raw.station_status_snapshots",
                        "reason": f"Load failed: {e}",
                        "raw_payload": json.dumps(station, ensure_ascii=False),
                    },
                )
                rejected_count += 1
            except Exception as reject_error:
                logger.error(
                    f"Failed to log rejected record to database: {reject_error}"
                )

    if loaded_count == 0 and len(stations) > 0:
        raise RuntimeError(
            f"No station_status raw records were loaded. "
            f"total_input={len(stations)}, rejected_count={rejected_count}"
        )

    logger.info(
        f"Raw station status loading completed. "
        f"loaded_or_upserted={loaded_count}, rejected={rejected_count}"
    )

    return loaded_count