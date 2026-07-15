import uuid

from src.common.config import get_settings
from src.common.db import fetch_one
from src.common.logger import get_logger
from src.extract.gbfs_client import GBFSClient
from src.load.raw_loader import load_gbfs_raw
from src.transform.metadata_transformer import (
    transform_regions,
    transform_stations,
    transform_system_information,
    transform_vehicle_types,
)

logger = get_logger(__name__)


def run_metadata_smoke_test():
    """
    Smoke test for metadata ETL.

    Scope:
    GBFSClient
    -> load_gbfs_raw
    -> raw.gbfs_feed_snapshots
    -> transform metadata
    -> staging tables
    """
    settings = get_settings()

    logger.info("Initializing metadata smoke test: Extract -> Raw Load -> Transform")
    logger.info(f"GBFS Base URL: {settings.GBFS_BASE_URL}")

    client = GBFSClient(settings.GBFS_BASE_URL)

    batch_id = f"manual-metadata-etl-{uuid.uuid4()}"
    logger.info(f"Generated Batch ID: {batch_id}")

    feeds = [
        "system_information",
        "system_regions",
        "vehicle_types",
        "station_information",
    ]

    total_loaded_by_function = 0
    failed_feeds = []

    # 1. Extract and raw load
    for feed_name in feeds:
        try:
            logger.info(f"--- Fetching feed: {feed_name} ---")

            payload = client.fetch_feed(feed_name)

            row_count = load_gbfs_raw(
                feed_name=feed_name,
                payload=payload,
                batch_id=batch_id,
                language=settings.GBFS_LANGUAGE,
            )

            total_loaded_by_function += row_count

            logger.info(f"Loaded {row_count} raw row for feed '{feed_name}'.")

        except Exception as e:
            logger.error(f"Failed to process feed '{feed_name}': {e}")
            failed_feeds.append(feed_name)

    if failed_feeds:
        raise RuntimeError(f"Raw ingestion failed. Failed feeds: {failed_feeds}")

    result = fetch_one(
        """
        SELECT COUNT(*) AS total
        FROM raw.gbfs_feed_snapshots
        WHERE batch_id = :batch_id
        """,
        {"batch_id": batch_id},
    )

    total_in_db = result["total"] if result else 0

    if total_loaded_by_function != len(feeds):
        raise RuntimeError(
            f"Raw ingestion check failed. Expected {len(feeds)} rows loaded by function, "
            f"but got {total_loaded_by_function}."
        )

    if total_in_db != len(feeds):
        raise RuntimeError(
            f"Raw ingestion check failed. Expected {len(feeds)} rows in database, "
            f"but found {total_in_db}."
        )

    logger.info("Raw ingestion completed successfully.")
    logger.info(f"Total raw rows in database for batch '{batch_id}': {total_in_db}")

    # 2. Transform raw to staging
    logger.info("==========================================================")
    logger.info("Starting transformation phase: Raw -> Staging")
    logger.info("==========================================================")

    try:
        transformed_sys_info = transform_system_information(batch_id)
        transformed_regions = transform_regions(batch_id)
        transformed_vehicle_types = transform_vehicle_types(batch_id)
        transformed_stations = transform_stations(batch_id)

    except Exception as e:
        logger.error(f"Transformation phase encountered an error: {e}")
        raise

    # 3. Validate transform result
    if transformed_sys_info != 1:
        raise RuntimeError(
            f"Expected 1 system_information record, got {transformed_sys_info}."
        )

    if transformed_regions <= 0:
        raise RuntimeError(
            f"Expected at least 1 region record, got {transformed_regions}."
        )

    if transformed_vehicle_types <= 0:
        raise RuntimeError(
            f"Expected at least 1 vehicle_type record, got {transformed_vehicle_types}."
        )

    if transformed_stations <= 0:
        raise RuntimeError(
            f"Expected at least 1 station record, got {transformed_stations}."
        )

    # 4. Print final summary
    logger.info("==========================================================")
    logger.info("Metadata Smoke Test Summary: Extract -> Raw Load -> Transform")
    logger.info(f"  - Batch ID: {batch_id}")
    logger.info(f"  - Expected raw feeds: {len(feeds)}")
    logger.info(f"  - Total loaded by function: {total_loaded_by_function}")
    logger.info(f"  - Total raw rows in database: {total_in_db}")
    logger.info(f"  - Staging system_information loaded: {transformed_sys_info}")
    logger.info(f"  - Staging regions loaded: {transformed_regions}")
    logger.info(f"  - Staging vehicle_types loaded: {transformed_vehicle_types}")
    logger.info(f"  - Staging stations loaded: {transformed_stations}")
    logger.info("==========================================================")
    logger.info("Metadata smoke test completed successfully.")


if __name__ == "__main__":
    run_metadata_smoke_test()