import json
import hashlib
from typing import Dict, Any
from src.common.db import execute_sql
from src.common.time_utils import utc_now, safe_timestamp_from_gbfs
from src.common.logger import get_logger

logger = get_logger(__name__)

def compute_payload_hash(payload: Dict[str, Any]) -> str:
    """
    Compute SHA256 hash of a JSON payload.
    Keys are sorted to guarantee consistent hash values.
    """
    serialized = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()

def load_gbfs_raw(feed_name: str, payload: Dict[str, Any], batch_id: str, language: str = "en") -> int:
    """
    Insert a raw GBFS feed payload snapshot into raw.gbfs_feed_snapshots.
    Returns 1 if successful, raises an exception on error.
    """
    logger.info(f"Loading raw snapshot for feed: {feed_name} | batch_id: {batch_id}")
    
    try:
        fetched_at = utc_now()
        ttl = payload.get("ttl")
        
        # Safely convert last_updated Unix timestamp to datetime in UTC
        last_updated_raw = payload.get("last_updated")
        source_last_updated = safe_timestamp_from_gbfs(last_updated_raw)
        
        payload_hash = compute_payload_hash(payload)
        
        # Serialize raw payload dict to string to be saved as JSONB
        raw_payload_str = json.dumps(payload)
        
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
                :raw_payload,
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
            "payload_hash": payload_hash
        }
        
        row_count = execute_sql(sql, params)
        logger.info(f"Successfully loaded {row_count} raw record for '{feed_name}'")
        return row_count
        
    except Exception as e:
        logger.error(f"Failed to load raw snapshot for '{feed_name}': {e}")
        raise
