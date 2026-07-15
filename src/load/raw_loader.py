import hashlib
import json
from typing import Any, Dict

from src.common.db import execute_sql
from src.common.logger import get_logger
from src.common.time_utils import safe_timestamp_from_gbfs, utc_now

logger = get_logger(__name__)


def compute_payload_hash(payload: Dict[str, Any]) -> str:
    """
    Compute SHA256 hash of a JSON payload.

    Keys are sorted and unnecessary spaces are removed
    to make the hash stable for logically identical JSON payloads.
    """
    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def load_gbfs_raw(
    feed_name: str,
    payload: Dict[str, Any],
    batch_id: str,
    language: str = "en",
) -> int:
    """
    Insert a raw GBFS feed payload snapshot into raw.gbfs_feed_snapshots.

    Returns the number of inserted rows.
    Raises an exception if loading fails.
    """
    logger.info(f"Loading raw snapshot for feed: {feed_name} | batch_id: {batch_id}")

    try:
        fetched_at = utc_now()

        ttl = payload.get("ttl")

        source_last_updated = safe_timestamp_from_gbfs(
            payload.get("last_updated")
        )

        payload_hash = compute_payload_hash(payload)

        raw_payload_str = json.dumps(
            payload,
            ensure_ascii=False,
        )

        sql = """
            INSERT INTO raw.gbfs_feed_snapshots (
                batch_id,
                feed_name,
                language,
                fetched_at,
                source_last_updated,
                ttl,
                raw_payload,
                payload_hash
            ) VALUES (
                :batch_id,
                :feed_name,
                :language,
                :fetched_at,
                :source_last_updated,
                :ttl,
                CAST(:raw_payload AS JSONB),
                :payload_hash
            )
        """

        params = {
            "batch_id": batch_id,
            "feed_name": feed_name,
            "language": language,
            "fetched_at": fetched_at,
            "source_last_updated": source_last_updated,
            "ttl": ttl,
            "raw_payload": raw_payload_str,
            "payload_hash": payload_hash,
        }

        row_count = execute_sql(sql, params)

        logger.info(
            f"Successfully loaded {row_count} raw record for feed '{feed_name}'"
        )

        return row_count

    except Exception as e:
        logger.error(f"Failed to load raw snapshot for feed '{feed_name}': {e}")
        raise