import uuid

from src.common.config import get_settings
from src.common.db import fetch_one
from src.common.logger import get_logger
from src.extract.gbfs_client import GBFSClient
from src.load.raw_loader import load_gbfs_raw

logger = get_logger(__name__)


def run_metadata_smoke_test():
    """
    Smoke test to fetch the 4 GBFS metadata feeds and load them into PostgreSQL.
    Scope:
    GBFSClient -> load_gbfs_raw -> raw.gbfs_feed_snapshots
    """
    settings = get_settings()

    logger.info("Initializing metadata smoke test...")
    logger.info(f"GBFS Base URL: {settings.GBFS_BASE_URL}")

    client = GBFSClient(settings.GBFS_BASE_URL)

    batch_id = f"manual-raw-metadata-{uuid.uuid4()}"
    logger.info(f"Generated Batch ID: {batch_id}")

    feeds = [
        "system_information",
        "system_regions",
        "vehicle_types",
        "station_information",
    ]

    total_loaded_by_function = 0
    failed_feeds = []

    for feed in feeds:
        try:
            logger.info(f"--- Fetching feed: {feed} ---")

            payload = client.fetch_feed(feed)

            row_count = load_gbfs_raw(
                feed_name=feed,
                payload=payload,
                batch_id=batch_id,
                language=settings.GBFS_LANGUAGE,
            )

            total_loaded_by_function += row_count

            logger.info(f"Loaded {row_count} row for feed '{feed}'.")

        except Exception as e:
            logger.error(f"Failed to process feed '{feed}': {e}")
            failed_feeds.append(feed)

    result = fetch_one(
        """
        SELECT COUNT(*) AS total
        FROM raw.gbfs_feed_snapshots
        WHERE batch_id = :batch_id
        """,
        {"batch_id": batch_id},
    )

    total_in_db = result["total"] if result else 0

    logger.info("==========================================================")
    logger.info("Smoke Test Summary:")
    logger.info(f"  - Batch ID: {batch_id}")
    logger.info(f"  - Total expected feeds: {len(feeds)}")
    logger.info(f"  - Total loaded by function: {total_loaded_by_function}")
    logger.info(f"  - Total rows in database: {total_in_db}")
    logger.info(f"  - Failed feeds: {failed_feeds}")
    logger.info("==========================================================")

    if failed_feeds:
        raise RuntimeError(f"Smoke test failed. Failed feeds: {failed_feeds}")

    if total_loaded_by_function != len(feeds):
        raise RuntimeError(
            f"Smoke test failed. Expected {len(feeds)} loaded rows, "
            f"but function returned {total_loaded_by_function}."
        )

    if total_in_db != len(feeds):
        raise RuntimeError(
            f"Smoke test failed. Expected {len(feeds)} rows in database, "
            f"but found {total_in_db}."
        )

    logger.info("Metadata smoke test completed successfully.")


if __name__ == "__main__":
    run_metadata_smoke_test()