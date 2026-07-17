from src.common.db import execute_sql
from src.common.logger import get_logger

logger = get_logger(__name__)


def start_pipeline_run(run_id: str, dag_id: str) -> None:
    """
    Record the start of a pipeline run.

    If the run_id already exists, reset it to running state.
    This is useful for manual reruns or Airflow retries.
    """
    logger.info(f"Recording start of pipeline run '{run_id}' for DAG '{dag_id}'")

    sql = """
        INSERT INTO etl_metadata.pipeline_runs (
            run_id,
            dag_id,
            status,
            started_at,
            ended_at,
            duration_seconds,
            records_extracted,
            records_loaded,
            records_rejected,
            error_message
        ) VALUES (
            :run_id,
            :dag_id,
            'running',
            CURRENT_TIMESTAMP,
            NULL,
            NULL,
            0,
            0,
            0,
            NULL
        )
        ON CONFLICT (run_id) DO UPDATE SET
            dag_id = EXCLUDED.dag_id,
            status = 'running',
            started_at = CURRENT_TIMESTAMP,
            ended_at = NULL,
            duration_seconds = NULL,
            records_extracted = 0,
            records_loaded = 0,
            records_rejected = 0,
            error_message = NULL
    """

    execute_sql(
        sql,
        {
            "run_id": run_id,
            "dag_id": dag_id,
        },
    )


def finish_pipeline_run_success(
    run_id: str,
    records_extracted: int = 0,
    records_loaded: int = 0,
    records_rejected: int = 0,
) -> None:
    """
    Record successful completion of a pipeline run and compute its duration.
    """
    logger.info(
        f"Recording successful pipeline run completion for '{run_id}'. "
        f"records_extracted={records_extracted}, "
        f"records_loaded={records_loaded}, "
        f"records_rejected={records_rejected}"
    )

    sql = """
        UPDATE etl_metadata.pipeline_runs
        SET status = 'success',
            ended_at = CURRENT_TIMESTAMP,
            duration_seconds = EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - started_at)),
            records_extracted = :records_extracted,
            records_loaded = :records_loaded,
            records_rejected = :records_rejected,
            error_message = NULL
        WHERE run_id = :run_id
    """

    execute_sql(
        sql,
        {
            "run_id": run_id,
            "records_extracted": records_extracted,
            "records_loaded": records_loaded,
            "records_rejected": records_rejected,
        },
    )


def finish_pipeline_run_failed(run_id: str, error_message: str) -> None:
    """
    Record failure of a pipeline run and save the error message.
    """
    logger.error(f"Recording pipeline run failure for '{run_id}': {error_message}")

    sql = """
        UPDATE etl_metadata.pipeline_runs
        SET status = 'failed',
            ended_at = CURRENT_TIMESTAMP,
            duration_seconds = EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - started_at)),
            error_message = :error_message
        WHERE run_id = :run_id
    """

    execute_sql(
        sql,
        {
            "run_id": run_id,
            "error_message": error_message,
        },
    )