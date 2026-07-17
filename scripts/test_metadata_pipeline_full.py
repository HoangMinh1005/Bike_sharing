import uuid

from src.common.config import get_settings
from src.common.db import fetch_one
from src.common.logger import get_logger
from src.common.time_utils import utc_now
from src.extract.gbfs_client import GBFSClient
from src.load.raw_loader import load_gbfs_raw
from src.metadata.pipeline_run_tracker import (
    finish_pipeline_run_failed,
    finish_pipeline_run_success,
    start_pipeline_run,
)
from src.metadata.watermark_manager import update_watermark
from src.quality.metadata_checks import run_metadata_dq_checks
from src.transform.metadata_transformer import (
    transform_regions,
    transform_stations,
    transform_system_information,
    transform_vehicle_types,
)

logger = get_logger(__name__)


def run_full_metadata_pipeline():
    """
    Orchestrate and test the complete metadata ETL pipeline lifecycle.

    Steps:
    1. Start pipeline run tracking
    2. Extract and raw load GBFS metadata feeds
    3. Transform raw data into staging tables
    4. Run raw + staging data quality checks
    5. Update watermark after successful DQ
    6. Mark pipeline run as success or failed
    """
    settings = get_settings()

    dag_id = "test_metadata_pipeline_full"
    run_id = f"manual-metadata-pipeline-{uuid.uuid4()}"

    # For this smoke test, use run_id as batch_id.
    # Later in Airflow, run_id and batch_id can be separated if needed.
    batch_id = run_id

    logger.info(f"Initializing full metadata pipeline run. run_id={run_id}")
    start_pipeline_run(run_id=run_id, dag_id=dag_id)

    feeds = [
        "system_information",
        "system_regions",
        "vehicle_types",
        "station_information",
    ]

    records_extracted = 0
    raw_records_loaded = 0

    try:
        # 1. Extract and raw load phase
        logger.info("==========================================================")
        logger.info("Starting raw ingestion phase")
        logger.info("==========================================================")

        client = GBFSClient(settings.GBFS_BASE_URL)

        for feed_name in feeds:
            logger.info(f"--- Ingesting raw feed: {feed_name} ---")

            payload = client.fetch_feed(feed_name)
            records_extracted += 1

            row_count = load_gbfs_raw(
                feed_name=feed_name,
                payload=payload,
                batch_id=batch_id,
                language=settings.GBFS_LANGUAGE,
            )

            raw_records_loaded += row_count

            logger.info(
                f"Loaded {row_count} raw row for feed '{feed_name}'."
            )

        if records_extracted != len(feeds):
            raise RuntimeError(
                f"Expected to extract {len(feeds)} feeds, "
                f"but extracted {records_extracted}."
            )

        if raw_records_loaded != len(feeds):
            raise RuntimeError(
                f"Expected to load {len(feeds)} raw rows, "
                f"but loaded {raw_records_loaded}."
            )

        logger.info(
            f"Raw ingestion completed successfully. "
            f"records_extracted={records_extracted}, "
            f"raw_records_loaded={raw_records_loaded}"
        )

        # 2. Transform raw to staging
        logger.info("==========================================================")
        logger.info("Starting staging transformation phase")
        logger.info("==========================================================")

        transformed_sys_info = transform_system_information(batch_id)
        transformed_regions = transform_regions(batch_id)
        transformed_vehicle_types = transform_vehicle_types(batch_id)
        transformed_stations = transform_stations(batch_id)

        if transformed_sys_info <= 0:
            raise RuntimeError("No system_information record was transformed.")

        if transformed_regions <= 0:
            raise RuntimeError("No region records were transformed.")

        if transformed_vehicle_types <= 0:
            raise RuntimeError("No vehicle_type records were transformed.")

        if transformed_stations <= 0:
            raise RuntimeError("No station records were transformed.")

        total_staging_loaded = (
            transformed_sys_info
            + transformed_regions
            + transformed_vehicle_types
            + transformed_stations
        )

        logger.info(
            f"Staging transformation completed. "
            f"total_staging_loaded={total_staging_loaded}"
        )

        # 3. Data quality checks
        logger.info("==========================================================")
        logger.info("Starting data quality checks phase")
        logger.info("==========================================================")

        run_metadata_dq_checks(
            run_id=run_id,
            batch_id=batch_id,
        )

        # 4. Update watermark after successful DQ
        logger.info("==========================================================")
        logger.info("Updating ingestion watermark")
        logger.info("==========================================================")

        watermark_val_row = fetch_one(
            """
            SELECT MAX(source_last_updated) AS max_updated
            FROM raw.gbfs_feed_snapshots
            WHERE batch_id = :batch_id
            """,
            {"batch_id": batch_id},
        )

        if watermark_val_row and watermark_val_row["max_updated"]:
            watermark_value = watermark_val_row["max_updated"].isoformat()
        else:
            watermark_value = utc_now().isoformat()

        update_watermark(
            source_name="gbfs_metadata",
            last_successful_value=watermark_value,
        )

        # 5. Finish successfully
        finish_pipeline_run_success(
            run_id=run_id,
            records_extracted=records_extracted,
            records_loaded=total_staging_loaded,
        )

        logger.info("==========================================================")
        logger.info("Metadata ETL pipeline completed successfully.")
        logger.info(f"run_id={run_id}")
        logger.info(f"batch_id={batch_id}")
        logger.info(f"records_extracted={records_extracted}")
        logger.info(f"raw_records_loaded={raw_records_loaded}")
        logger.info(f"total_staging_loaded={total_staging_loaded}")
        logger.info(f"watermark_value={watermark_value}")
        logger.info("==========================================================")

    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}")

        finish_pipeline_run_failed(
            run_id=run_id,
            error_message=str(e),
        )

        raise


if __name__ == "__main__":
    run_full_metadata_pipeline()