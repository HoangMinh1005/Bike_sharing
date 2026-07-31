from typing import List, Optional
from fastapi import HTTPException, status

from src.common.db import fetch_all, fetch_one
from src.common.logger import get_logger

logger = get_logger(__name__)


def get_latest_pipeline_health() -> List[dict]:
    """
    Fetch latest pipeline health summary for all monitored DAGs.

    Source: etl_metadata.pipeline_health_summary
    """
    sql = """
        SELECT *
        FROM etl_metadata.pipeline_health_summary
        WHERE health_run_id = (
            SELECT health_run_id
            FROM etl_metadata.pipeline_health_summary
            ORDER BY checked_at DESC
            LIMIT 1
        )
        ORDER BY monitored_dag_id ASC
    """
    return fetch_all(sql)


def get_pipeline_health_history(
    dag_id: str,
    limit: int = 24,
) -> List[dict]:
    """
    Fetch historical health monitoring summary rows for a specific monitored DAG.

    Source: etl_metadata.pipeline_health_summary
    """
    sql = """
        SELECT *
        FROM etl_metadata.pipeline_health_summary
        WHERE monitored_dag_id = :dag_id
        ORDER BY checked_at DESC
        LIMIT :limit
    """
    records = fetch_all(sql, {"dag_id": dag_id, "limit": limit})
    if not records:
        exists = fetch_one(
            "SELECT 1 FROM etl_metadata.pipeline_health_summary WHERE monitored_dag_id = :dag_id LIMIT 1",
            {"dag_id": dag_id},
        )
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": f"Monitored DAG '{dag_id}' not found."},
            )
    return records


def get_pipeline_health_by_status(health_status: str) -> List[dict]:
    """
    Fetch monitored pipelines with a specific health_status from latest health run.

    Source: etl_metadata.pipeline_health_summary
    """
    status_clean = health_status.upper()
    valid_statuses = ("HEALTHY", "WARNING", "FAILED", "STALE", "UNKNOWN")
    if status_clean not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "BAD_REQUEST",
                "message": f"Invalid health_status '{health_status}'. Allowed: {list(valid_statuses)}.",
            },
        )

    sql = """
        SELECT *
        FROM etl_metadata.pipeline_health_summary
        WHERE health_run_id = (
            SELECT health_run_id
            FROM etl_metadata.pipeline_health_summary
            ORDER BY checked_at DESC
            LIMIT 1
        )
        AND health_status = :health_status
        ORDER BY monitored_dag_id ASC
    """
    return fetch_all(sql, {"health_status": status_clean})


def get_latest_pipeline_runs() -> List[dict]:
    """
    Fetch latest run execution entry for each DAG across the system.

    Source: etl_metadata.pipeline_runs
    """
    sql = """
        SELECT DISTINCT ON (dag_id)
            run_id,
            dag_id,
            task_name,
            status,
            started_at,
            ended_at,
            duration_seconds,
            records_extracted,
            records_loaded,
            records_rejected,
            error_message
        FROM etl_metadata.pipeline_runs
        ORDER BY dag_id, started_at DESC NULLS LAST
    """
    return fetch_all(sql)
