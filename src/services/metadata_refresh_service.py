"""
Metadata Refresh Service for Controlled Self-Healing.

Provides reusable functions to fetch, raw-load, and transform GBFS metadata feeds
(specifically station_information and system_regions) on-demand when metadata drift is detected.
"""
from typing import Any, Dict

from src.common.config import get_settings
from src.common.logger import get_logger
from src.extract.gbfs_client import GBFSClient
from src.load.raw_loader import load_gbfs_raw
from src.transform.metadata_transformer import (
    transform_regions,
    transform_stations,
)

logger = get_logger(__name__)


def refresh_gbfs_station_metadata(
    batch_id: str,
    reason: str = "metadata_drift_self_healing",
) -> Dict[str, Any]:
    """
    Fetch raw metadata from GBFS API, store raw snapshots, and transform into staging tables.

    Scope:
    - system_regions (required as foreign key for station_information)
    - station_information

    Idempotence:
    - Uses upsert logic in transform_regions and transform_stations.
    - Idempotent and safe to run inline during pipeline execution.

    Returns:
        dict containing refreshed count summary.
    """
    settings = get_settings()

    logger.info(
        f"Starting controlled GBFS station metadata refresh. "
        f"batch_id={batch_id}, reason={reason}"
    )

    client = GBFSClient(settings.GBFS_BASE_URL)
    feeds_to_refresh = ["system_regions", "station_information"]

    raw_loaded = {}

    for feed_name in feeds_to_refresh:
        logger.info(f"Self-healing: fetching metadata feed '{feed_name}'...")
        payload = client.fetch_feed(feed_name)

        count = load_gbfs_raw(
            feed_name=feed_name,
            payload=payload,
            batch_id=batch_id,
            language=settings.GBFS_LANGUAGE,
        )
        raw_loaded[feed_name] = count

    logger.info(f"Self-healing: transforming regions for batch_id={batch_id}...")
    transformed_regions = transform_regions(batch_id)

    logger.info(f"Self-healing: transforming stations for batch_id={batch_id}...")
    transformed_stations = transform_stations(batch_id)

    logger.info(
        f"Controlled station metadata refresh completed successfully. "
        f"batch_id={batch_id}, regions={transformed_regions}, stations={transformed_stations}"
    )

    return {
        "batch_id": batch_id,
        "reason": reason,
        "raw_loaded": raw_loaded,
        "transformed_regions": transformed_regions,
        "transformed_stations": transformed_stations,
    }
