import pendulum

from airflow.decorators import dag, task

from src.common.logger import get_logger

logger = get_logger(__name__)


default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 0,
}


@dag(
    dag_id="station_status_snapshot_dag",
    default_args=default_args,
    description="ETL pipeline for GBFS station_status snapshots every 15 minutes",
    schedule="*/15 * * * *",
    start_date=pendulum.datetime(2026, 7, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    tags=["gbfs", "station_status", "snapshot", "etl"],
)
def station_status_snapshot_dag():
    @task
    def start_pipeline() -> dict:
        """
        1. Initialize pipeline run tracking.
        """
        from airflow.operators.python import get_current_context
        from src.metadata.pipeline_run_tracker import start_pipeline_run

        context = get_current_context()

        dag_id = context["dag"].dag_id
        run_id = context["run_id"]
        batch_id = run_id

        logger.info(
            f"Starting station_status pipeline run. "
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
        2. Clean existing raw and staging records for the active batch_id.

        This makes rerun safer when an Airflow task is cleared and executed again
        with the same run_id / batch_id.
        """
        from src.common.db import execute_sql
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed

        run_id = batch_info["run_id"]
        batch_id = batch_info["batch_id"]

        try:
            logger.info(
                f"Cleaning existing station_status records for batch_id={batch_id}"
            )

            deleted_vehicle_type_status = execute_sql(
                """
                DELETE FROM staging.station_vehicle_type_status
                WHERE batch_id = :batch_id
                """,
                {
                    "batch_id": batch_id,
                },
            )

            deleted_station_status = execute_sql(
                """
                DELETE FROM staging.station_status
                WHERE batch_id = :batch_id
                """,
                {
                    "batch_id": batch_id,
                },
            )

            deleted_raw = execute_sql(
                """
                DELETE FROM raw.station_status_snapshots
                WHERE batch_id = :batch_id
                  AND feed_name = 'station_status'
                """,
                {
                    "batch_id": batch_id,
                },
            )

            logger.info(
                f"Deleted existing records for batch_id={batch_id}: "
                f"staging.station_vehicle_type_status={deleted_vehicle_type_status}, "
                f"staging.station_status={deleted_station_status}, "
                f"raw.station_status_snapshots={deleted_raw}"
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
    def extract_and_load_station_status(batch_info: dict) -> dict:
        """
        3. Fetch station_status feed from GBFS API and load raw snapshots.

        Raw layer stores one row per station per snapshot.
        """
        from src.common.config import get_settings
        from src.extract.gbfs_client import GBFSClient
        from src.load.station_status_raw_loader import load_station_status_raw
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed

        settings = get_settings()

        run_id = batch_info["run_id"]
        batch_id = batch_info["batch_id"]

        try:
            logger.info("Extracting GBFS station_status feed...")

            client = GBFSClient(settings.GBFS_BASE_URL)
            payload = client.fetch_feed("station_status")

            raw_records_loaded = load_station_status_raw(
                payload=payload,
                batch_id=batch_id,
                run_id=run_id,
                language=settings.GBFS_LANGUAGE,
            )

            if raw_records_loaded <= 0:
                raise RuntimeError("No raw station_status records were loaded.")

            logger.info(
                f"Raw station_status ingestion completed successfully. "
                f"raw_records_loaded={raw_records_loaded}"
            )

            return {
                **batch_info,
                "records_extracted": 1,
                "raw_records_loaded": raw_records_loaded,
            }

        except Exception as e:
            logger.error(f"Error in extract_and_load_station_status task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Extract and load station_status failed: {e}",
            )

            raise

    @task
    def transform_station_status_task(batch_info: dict) -> dict:
        """
        4. Transform raw station_status snapshots into staging tables.
        """
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed
        from src.transform.station_status_transformer import (
            transform_station_status,
            transform_station_vehicle_type_status,
        )

        run_id = batch_info["run_id"]
        batch_id = batch_info["batch_id"]

        try:
            logger.info("Transforming staging.station_status...")
            transformed_status = transform_station_status(batch_id)

            logger.info("Transforming staging.station_vehicle_type_status...")
            transformed_vehicle_type_status = transform_station_vehicle_type_status(
                batch_id
            )

            if transformed_status <= 0:
                raise RuntimeError("No station_status record was transformed.")

            records_loaded = transformed_status + transformed_vehicle_type_status

            logger.info(
                f"Station_status transformation completed successfully. "
                f"station_status={transformed_status}, "
                f"vehicle_type_status={transformed_vehicle_type_status}, "
                f"records_loaded={records_loaded}"
            )

            return {
                **batch_info,
                "records_loaded": records_loaded,
                "transformed_status": transformed_status,
                "transformed_vehicle_type_status": transformed_vehicle_type_status,
            }

        except Exception as e:
            logger.error(f"Error in transform_station_status_task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Station_status transformation failed: {e}",
            )

            raise

    @task
    def run_dq(batch_info: dict) -> dict:
        """
        5. Run data quality checks on raw and staging station_status tables.
        """
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed
        from src.quality.station_status_checks import run_station_status_dq_checks

        run_id = batch_info["run_id"]
        batch_id = batch_info["batch_id"]

        try:
            logger.info(
                f"Running station_status DQ checks. "
                f"run_id={run_id}, batch_id={batch_id}"
            )

            run_station_status_dq_checks(
                run_id=run_id,
                batch_id=batch_id,
            )

            logger.info("Station_status DQ checks completed successfully.")

            return batch_info

        except Exception as e:
            logger.error(f"Error in run_dq task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Station_status DQ checks failed: {e}",
            )

            raise

    @task
    def update_watermark_task(batch_info: dict) -> dict:
        """
        6. Update watermark after successful raw load, transform, and DQ.

        Watermark priority:
        1. MAX(source_last_updated)
        2. MAX(last_reported)
        3. MAX(fetched_at)
        4. current UTC timestamp as fallback
        """
        from src.common.db import fetch_one
        from src.metadata.pipeline_run_tracker import finish_pipeline_run_failed
        from src.metadata.watermark_manager import update_watermark

        run_id = batch_info["run_id"]
        batch_id = batch_info["batch_id"]

        try:
            logger.info(
                f"Extracting station_status watermark values for batch_id={batch_id}"
            )

            watermark_val_row = fetch_one(
                """
                SELECT
                    MAX(source_last_updated) AS max_source_updated,
                    MAX(last_reported) AS max_last_reported,
                    MAX(fetched_at) AS max_fetched
                FROM staging.station_status
                WHERE batch_id = :batch_id
                """,
                {
                    "batch_id": batch_id,
                },
            )

            watermark_value = None

            if watermark_val_row:
                if watermark_val_row["max_source_updated"]:
                    watermark_value = watermark_val_row[
                        "max_source_updated"
                    ].isoformat()
                elif watermark_val_row["max_last_reported"]:
                    watermark_value = watermark_val_row[
                        "max_last_reported"
                    ].isoformat()
                elif watermark_val_row["max_fetched"]:
                    watermark_value = watermark_val_row[
                        "max_fetched"
                    ].isoformat()

            if not watermark_value:
                watermark_value = pendulum.now("UTC").isoformat()

            logger.info(
                f"Updating station_status watermark. "
                f"source_name=gbfs_station_status, value={watermark_value}"
            )

            update_watermark(
                source_name="gbfs_station_status",
                last_successful_value=watermark_value,
            )

            return {
                **batch_info,
                "watermark_value": watermark_value,
            }

        except Exception as e:
            logger.error(f"Error in update_watermark_task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Station_status watermark update failed: {e}",
            )

            raise

    @task
    def finish_pipeline(batch_info: dict) -> None:
        """
        7. Mark pipeline run as success.
        """
        from src.common.db import fetch_one
        from src.metadata.pipeline_run_tracker import (
            finish_pipeline_run_failed,
            finish_pipeline_run_success,
        )

        run_id = batch_info["run_id"]
        records_extracted = batch_info.get("records_extracted", 0)
        records_loaded = batch_info.get("records_loaded", 0)
        watermark_value = batch_info.get("watermark_value")

        try:
            rejected_row = fetch_one(
                """
                SELECT COUNT(*) AS rejected_count
                FROM etl_metadata.rejected_records
                WHERE run_id = :run_id
                  AND source_name = 'gbfs_station_status'
                """,
                {
                    "run_id": run_id,
                },
            )

            records_rejected = (
                int(rejected_row["rejected_count"])
                if rejected_row and rejected_row["rejected_count"] is not None
                else 0
            )

            logger.info(
                f"Marking station_status pipeline run as success. "
                f"run_id={run_id}, "
                f"records_extracted={records_extracted}, "
                f"records_loaded={records_loaded}, "
                f"records_rejected={records_rejected}, "
                f"watermark={watermark_value}"
            )

            finish_pipeline_run_success(
                run_id=run_id,
                records_extracted=records_extracted,
                records_loaded=records_loaded,
                records_rejected=records_rejected,
            )

            logger.info(
                f"Station_status pipeline run completed successfully. "
                f"run_id={run_id}"
            )

        except Exception as e:
            logger.error(f"Error in finish_pipeline task: {e}")

            finish_pipeline_run_failed(
                run_id=run_id,
                error_message=f"Finish station_status pipeline tracking failed: {e}",
            )

            raise

    batch_info_flow = start_pipeline()
    batch_info_flow = prepare_batch_for_rerun(batch_info_flow)
    batch_info_flow = extract_and_load_station_status(batch_info_flow)
    batch_info_flow = transform_station_status_task(batch_info_flow)
    batch_info_flow = run_dq(batch_info_flow)
    batch_info_flow = update_watermark_task(batch_info_flow)
    finish_pipeline(batch_info_flow)


dag_instance = station_status_snapshot_dag()