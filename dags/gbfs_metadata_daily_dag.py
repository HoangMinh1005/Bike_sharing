import pendulum

from airflow.decorators import dag, task

from src.common.logger import get_logger

logger = get_logger(__name__)


METADATA_FEEDS = [
    "system_information",
    "system_regions",
    "vehicle_types",
    "station_information",
]


default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 0,
}


@dag(
    dag_id="gbfs_metadata_daily_dag",
    default_args=default_args,
    description=(
        "Daily GBFS metadata ETL pipeline "
        "(Extract -> Load Raw -> Transform Staging -> DQ -> Watermark)"
    ),
    schedule="@daily",
    start_date=pendulum.datetime(2026, 7, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    tags=["gbfs", "metadata", "etl"],
)
def gbfs_metadata_daily_dag():
    @task
    def start_pipeline() -> dict:
        """
        1. Initialize pipeline run tracking.

        This task creates or resets the pipeline run record.
        Airflow run_id is also used as batch_id so all data produced
        by this run can be traced together.
        """
        from airflow.operators.python import get_current_context
        from src.metadata.pipeline_run_tracker import start_pipeline_run

        context = get_current_context()

        dag_id = context["dag"].dag_id
        run_id = context["run_id"]
        batch_id = run_id

        logger.info(
            f"Starting metadata pipeline. "
            f"dag_id={dag_id}, run_id={run_id}, batch_id={batch_id}"
        )

        start_pipeline_run(
            run_id=run_id,
            dag_id=dag_id,
        )

        return {
            "run_id": run_id,
            "batch_id": batch_id,
        }

    @task
    def prepare_batch_for_rerun(batch_info: dict) -> dict:
        """
        2. Clean existing raw records for the same batch_id before rerun.

        Why this exists:
        - In Airflow, if a task is cleared and rerun, the run_id usually stays the same.
        - Since this DAG uses run_id as batch_id, rerunning extract/load with the same
          batch_id can duplicate raw records if raw layer has no unique constraint yet.
        - This cleanup only deletes records of the current batch_id and metadata feeds,
          so it does not affect previous successful pipeline runs.

        Note:
        - Staging tables are handled by UPSERT in transformer logic.
        - For a stronger production design, raw tables should also have a unique
          constraint such as (batch_id, feed_name, language).
        """
        from src.common.db import execute_sql
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed

        run_id = batch_info["run_id"]
        batch_id = batch_info["batch_id"]

        try:
            logger.info(
                f"Preparing metadata batch for rerun. "
                f"batch_id={batch_id}"
            )

            deleted_count = execute_sql(
                """
                DELETE FROM raw.gbfs_feed_snapshots
                WHERE batch_id = :batch_id
                  AND feed_name IN (
                      'system_information',
                      'system_regions',
                      'vehicle_types',
                      'station_information'
                  )
                """,
                {
                    "batch_id": batch_id,
                },
            )

            logger.info(
                f"Deleted {deleted_count} existing raw metadata record(s) "
                f"for batch_id={batch_id}."
            )

            return batch_info

        except Exception as e:
            logger.error(f"Error in prepare_batch_for_rerun task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Prepare batch for rerun failed: {e}",
            )

            raise

    @task
    def extract_and_load(batch_info: dict) -> dict:
        """
        3. Extract metadata feeds from GBFS API and load raw snapshots.

        Expected feeds:
        - system_information
        - system_regions
        - vehicle_types
        - station_information
        """
        from src.common.config import get_settings
        from src.extract.gbfs_client import GBFSClient
        from src.load.raw_loader import load_gbfs_raw
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed

        settings = get_settings()

        run_id = batch_info["run_id"]
        batch_id = batch_info["batch_id"]

        records_extracted = 0
        raw_records_loaded = 0

        try:
            client = GBFSClient(settings.GBFS_BASE_URL)

            for feed_name in METADATA_FEEDS:
                logger.info(f"Extracting GBFS metadata feed: {feed_name}")

                payload = client.fetch_feed(feed_name)
                records_extracted += 1

                logger.info(
                    f"Loading raw snapshot for feed={feed_name}, "
                    f"batch_id={batch_id}"
                )

                row_count = load_gbfs_raw(
                    feed_name=feed_name,
                    payload=payload,
                    batch_id=batch_id,
                    language=settings.GBFS_LANGUAGE,
                )

                raw_records_loaded += row_count

                logger.info(
                    f"Loaded raw feed={feed_name}, row_count={row_count}"
                )

            expected_feed_count = len(METADATA_FEEDS)

            if records_extracted != expected_feed_count:
                raise RuntimeError(
                    f"Expected to extract {expected_feed_count} metadata feeds, "
                    f"but extracted {records_extracted}."
                )

            if raw_records_loaded != expected_feed_count:
                raise RuntimeError(
                    f"Expected to load {expected_feed_count} raw metadata rows, "
                    f"but loaded {raw_records_loaded}."
                )

            logger.info(
                f"Raw ingestion completed successfully. "
                f"records_extracted={records_extracted}, "
                f"raw_records_loaded={raw_records_loaded}"
            )

            return {
                **batch_info,
                "records_extracted": records_extracted,
                "raw_records_loaded": raw_records_loaded,
            }

        except Exception as e:
            logger.error(f"Error in extract_and_load task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Extract and load failed: {e}",
            )

            raise

    @task
    def transform(batch_info: dict) -> dict:
        """
        4. Transform raw JSON payloads into staging metadata tables.

        Important order:
        - transform_regions must run before transform_stations
          because stations may reference region_id.
        """
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed
        from src.transform.metadata_transformer import (
            transform_regions,
            transform_stations,
            transform_system_information,
            transform_vehicle_types,
        )

        run_id = batch_info["run_id"]
        batch_id = batch_info["batch_id"]

        try:
            logger.info("Transforming system_information...")
            transformed_system_information = transform_system_information(batch_id)

            logger.info("Transforming system_regions...")
            transformed_regions = transform_regions(batch_id)

            logger.info("Transforming vehicle_types...")
            transformed_vehicle_types = transform_vehicle_types(batch_id)

            logger.info("Transforming station_information...")
            transformed_stations = transform_stations(batch_id)

            if transformed_system_information <= 0:
                raise RuntimeError(
                    "No system_information record was transformed."
                )

            if transformed_regions <= 0:
                raise RuntimeError(
                    "No region records were transformed."
                )

            if transformed_vehicle_types <= 0:
                raise RuntimeError(
                    "No vehicle_type records were transformed."
                )

            if transformed_stations <= 0:
                raise RuntimeError(
                    "No station records were transformed."
                )

            records_loaded = (
                transformed_system_information
                + transformed_regions
                + transformed_vehicle_types
                + transformed_stations
            )

            logger.info(
                f"Transformation completed successfully. "
                f"system_information={transformed_system_information}, "
                f"regions={transformed_regions}, "
                f"vehicle_types={transformed_vehicle_types}, "
                f"stations={transformed_stations}, "
                f"records_loaded={records_loaded}"
            )

            return {
                **batch_info,
                "records_loaded": records_loaded,
                "transformed_system_information": transformed_system_information,
                "transformed_regions": transformed_regions,
                "transformed_vehicle_types": transformed_vehicle_types,
                "transformed_stations": transformed_stations,
            }

        except Exception as e:
            logger.error(f"Error in transform task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Transformation failed: {e}",
            )

            raise

    @task
    def run_dq(batch_info: dict) -> dict:
        """
        5. Run data quality checks on raw and staging metadata tables.
        """
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed
        from src.quality.metadata_checks import run_metadata_dq_checks

        run_id = batch_info["run_id"]
        batch_id = batch_info["batch_id"]

        try:
            logger.info(
                f"Running metadata data quality checks. "
                f"run_id={run_id}, batch_id={batch_id}"
            )

            run_metadata_dq_checks(
                run_id=run_id,
                batch_id=batch_id,
            )

            logger.info("Metadata data quality checks completed successfully.")

            return batch_info

        except Exception as e:
            logger.error(f"Error in run_dq task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"DQ checks failed: {e}",
            )

            raise

    @task
    def update_watermarks(batch_info: dict) -> dict:
        """
        6. Update watermark after successful raw load, transform, and DQ.

        Watermark is updated only after DQ passes.
        """
        from src.common.db import fetch_one
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed
        from src.metadata.watermark_manager import update_watermark

        run_id = batch_info["run_id"]
        batch_id = batch_info["batch_id"]

        try:
            logger.info(
                f"Extracting max source_last_updated for batch_id={batch_id}"
            )

            watermark_val_row = fetch_one(
                """
                SELECT MAX(source_last_updated) AS max_updated
                FROM raw.gbfs_feed_snapshots
                WHERE batch_id = :batch_id
                  AND feed_name IN (
                      'system_information',
                      'system_regions',
                      'vehicle_types',
                      'station_information'
                  )
                """,
                {
                    "batch_id": batch_id,
                },
            )

            if watermark_val_row and watermark_val_row["max_updated"]:
                watermark_value = watermark_val_row["max_updated"].isoformat()
            else:
                watermark_value = pendulum.now("UTC").isoformat()

            logger.info(
                f"Updating metadata watermark. "
                f"source_name=gbfs_metadata, watermark_value={watermark_value}"
            )

            update_watermark(
                source_name="gbfs_metadata",
                last_successful_value=watermark_value,
            )

            return {
                **batch_info,
                "watermark_value": watermark_value,
            }

        except Exception as e:
            logger.error(f"Error in update_watermarks task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Watermark update failed: {e}",
            )

            raise

    @task
    def finish_pipeline(batch_info: dict) -> None:
        """
        7. Mark pipeline run as success.
        """
        from src.metadata.pipeline_run_tracker import (
            finish_pipeline_run_failed,
            finish_pipeline_run_success,
        )

        run_id = batch_info["run_id"]
        records_extracted = batch_info.get("records_extracted", 0)
        records_loaded = batch_info.get("records_loaded", 0)
        records_rejected = batch_info.get("records_rejected", 0)
        watermark_value = batch_info.get("watermark_value")

        try:
            logger.info(
                f"Marking metadata pipeline as success. "
                f"run_id={run_id}, "
                f"records_extracted={records_extracted}, "
                f"records_loaded={records_loaded}, "
                f"records_rejected={records_rejected}, "
                f"watermark_value={watermark_value}"
            )

            finish_pipeline_run_success(
                run_id=run_id,
                records_extracted=records_extracted,
                records_loaded=records_loaded,
                records_rejected=records_rejected,
            )

            logger.info(
                f"Metadata pipeline completed successfully. run_id={run_id}"
            )

        except Exception as e:
            logger.error(f"Error in finish_pipeline task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Finish pipeline tracking failed: {e}",
            )

            raise

    batch_info_flow = start_pipeline()
    batch_info_flow = prepare_batch_for_rerun(batch_info_flow)
    batch_info_flow = extract_and_load(batch_info_flow)
    batch_info_flow = transform(batch_info_flow)
    batch_info_flow = run_dq(batch_info_flow)
    batch_info_flow = update_watermarks(batch_info_flow)
    finish_pipeline(batch_info_flow)


dag_instance = gbfs_metadata_daily_dag()