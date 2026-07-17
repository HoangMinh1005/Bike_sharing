import uuid

from src.common.config import get_settings
from src.common.db import fetch_one
from src.common.logger import get_logger
from src.extract.gbfs_client import GBFSClient
from src.load.raw_loader import load_gbfs_raw
from src.quality.metadata_checks import run_metadata_dq_checks
from src.transform.metadata_transformer import (
    transform_regions,
    transform_stations,
    transform_system_information,
    transform_vehicle_types,
)

logger = get_logger(__name__)


def run_metadata_smoke_test():
    """
    Metadata ETL smoke test.

    Scope:
    1. Generate batch_id
    2. Fetch 4 metadata feeds
    3. Load raw snapshots
    4. Validate raw rows
    5. Transform raw data into staging tables
    6. Run batch-aware data quality checks
    """
    settings = get_settings()

    logger.info(
        "Initializing metadata smoke test: "
        "Extract -> Raw Load -> Transform -> DQ Checks"
    )
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

    # 2. Validate raw rows
    result = fetch_one(
        """
        SELECT COUNT(*) AS total
        FROM raw.gbfs_feed_snapshots
        WHERE batch_id = :batch_id
        """,
        {"batch_id": batch_id},
    )

    total_in_db = int(result["total"] or 0) if result else 0

    if total_loaded_by_function != len(feeds):
        raise RuntimeError(
            f"Raw ingestion check failed. Expected {len(feeds)} rows loaded "
            f"by function, but got {total_loaded_by_function}."
        )

    if total_in_db != len(feeds):
        raise RuntimeError(
            f"Raw ingestion check failed. Expected {len(feeds)} rows in database, "
            f"but found {total_in_db}."
        )

    logger.info("Raw ingestion validated successfully.")

    # 3. Transform raw to staging
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

    if transformed_sys_info <= 0:
        raise RuntimeError("No system_information record was transformed.")

    if transformed_regions <= 0:
        raise RuntimeError("No region records were transformed.")

    if transformed_vehicle_types <= 0:
        raise RuntimeError("No vehicle_type records were transformed.")

    if transformed_stations <= 0:
        raise RuntimeError("No station records were transformed.")

    # 4. Run batch-aware DQ checks
    logger.info("==========================================================")
    logger.info("Starting Data Quality Checks Phase")
    logger.info("==========================================================")

    run_metadata_dq_checks(
        run_id=batch_id,
        batch_id=batch_id,
    )

    # 5. Final summary
    logger.info("==========================================================")
    logger.info("Metadata Smoke Test Summary:")
    logger.info(f"  - Batch ID: {batch_id}")
    logger.info(f"  - Total expected raw feeds: {len(feeds)}")
    logger.info(f"  - Total raw rows in database: {total_in_db}")
    logger.info(f"  - Staging system_information loaded: {transformed_sys_info}")
    logger.info(f"  - Staging regions loaded: {transformed_regions}")
    logger.info(f"  - Staging vehicle_types loaded: {transformed_vehicle_types}")
    logger.info(f"  - Staging stations loaded: {transformed_stations}")
    logger.info("==========================================================")
    logger.info("Metadata smoke test completed successfully.")


if __name__ == "__main__":
    run_metadata_smoke_test()