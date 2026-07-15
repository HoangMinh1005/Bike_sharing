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
    """
    settings = get_settings()
    logger.info("Initializing metadata smoke test...")
    logger.info(f"GBFS Base URL: {settings.GBFS_BASE_URL}")

    # Initialize GBFS Client
    client = GBFSClient(settings.GBFS_BASE_URL)

    # Generate a unique batch_id matching the manual-raw-metadata-{uuid} pattern
    batch_id = f"manual-raw-metadata-{uuid.uuid4()}"
    logger.info(f"Generated Batch ID: {batch_id}")

    feeds = [
        "system_information",
        "system_regions",
        "vehicle_types",
        "station_information"
    ]

    total_loaded_by_function = 0

    for feed in feeds:
        try:
            logger.info(f"--- Fetching feed: {feed} ---")
            payload = client.fetch_feed(feed)

            # Insert raw snapshot into the database
            row_count = load_gbfs_raw(
                feed_name=feed,
                payload=payload,
                batch_id=batch_id,
                language=settings.GBFS_LANGUAGE
            )
            total_loaded_by_function += row_count
            logger.info(f"Loaded {row_count} row for feed '{feed}'.")

        except Exception as e:
            logger.error(f"Failed to process feed '{feed}': {e}")

    # Query the database to count total rows loaded with this batch_id
    query = """
        SELECT COUNT(*) AS total
        FROM raw.gbfs_feed_snapshots
        WHERE batch_id = :batch_id
    """
    result = fetch_one(query, {"batch_id": batch_id})
    total_in_db = result["total"] if result else 0

    # Print final smoke test metrics
    logger.info("==========================================================")
    logger.info(f"Smoke Test Summary:")
    logger.info(f"  - Batch ID: {batch_id}")
    logger.info(f"  - Total loaded by function: {total_loaded_by_function}")
    logger.info(f"  - Total rows in database: {total_in_db}")
    logger.info("==========================================================")

if __name__ == "__main__":
    run_metadata_smoke_test()
