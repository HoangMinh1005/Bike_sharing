import uuid
import pytest
import pendulum

from src.common.db import execute_sql, fetch_one, fetch_all
from src.monitoring.pipeline_health_builder import (
    _validate_health_run_inputs,
    build_pipeline_health_summary,
    get_monitored_pipelines,
)
from src.quality.pipeline_health_checks import run_pipeline_health_dq_checks


@pytest.fixture
def clean_health_test_runs():
    health_run_ids = []
    pipeline_run_ids = []
    yield health_run_ids, pipeline_run_ids

    for h_id in health_run_ids:
        execute_sql(
            "DELETE FROM etl_metadata.pipeline_health_summary WHERE health_run_id = :run_id",
            {"run_id": h_id},
        )
        execute_sql(
            "DELETE FROM etl_metadata.dq_results WHERE run_id = :run_id",
            {"run_id": h_id},
        )
        execute_sql(
            "DELETE FROM etl_metadata.pipeline_runs WHERE run_id = :run_id",
            {"run_id": h_id},
        )

    for p_id in pipeline_run_ids:
        execute_sql(
            "DELETE FROM etl_metadata.dq_results WHERE run_id = :run_id",
            {"run_id": p_id},
        )
        execute_sql(
            "DELETE FROM etl_metadata.pipeline_runs WHERE run_id = :run_id",
            {"run_id": p_id},
        )


def test_validate_health_run_inputs():
    """Verify input validation for pipeline health summary build."""
    with pytest.raises(ValueError):
        _validate_health_run_inputs("", "batch-1", "2026-07-28T00:00:00Z")

    with pytest.raises(ValueError):
        _validate_health_run_inputs("run-1", " ", "2026-07-28T00:00:00Z")

    with pytest.raises(ValueError):
        _validate_health_run_inputs("run-1", "batch-1", "invalid-date")


def test_pipeline_health_summary_end_to_end_flow(clean_health_test_runs):
    """Test full building and DQ check flow for pipeline health monitoring."""
    health_run_ids, pipeline_run_ids = clean_health_test_runs
    health_run_id = f"test-health-run-{uuid.uuid4()}"
    health_run_ids.append(health_run_id)

    # 1. Insert mock successful run for gbfs_metadata_daily_dag
    mock_run_success = f"test-mock-success-{uuid.uuid4()}"
    pipeline_run_ids.append(mock_run_success)
    execute_sql(
        """
        INSERT INTO etl_metadata.pipeline_runs (
            run_id, dag_id, status, started_at, ended_at, duration_seconds,
            records_extracted, records_loaded, records_rejected
        ) VALUES (
            :run_id, 'gbfs_metadata_daily_dag', 'success',
            CURRENT_TIMESTAMP + INTERVAL '1 hour', CURRENT_TIMESTAMP + INTERVAL '1 hour 1 minute', 60,
            10, 10, 0
        )
        """,
        {"run_id": mock_run_success},
    )

    # 2. Insert mock failed run for station_status_snapshot_dag
    mock_run_failed = f"test-mock-failed-{uuid.uuid4()}"
    pipeline_run_ids.append(mock_run_failed)
    execute_sql(
        """
        INSERT INTO etl_metadata.pipeline_runs (
            run_id, dag_id, status, started_at, ended_at, duration_seconds,
            records_extracted, records_loaded, records_rejected, error_message
        ) VALUES (
            :run_id, 'station_status_snapshot_dag', 'failed',
            CURRENT_TIMESTAMP + INTERVAL '2 hours', CURRENT_TIMESTAMP + INTERVAL '2 hours 1 minute', 60,
            0, 0, 0, 'Mock connection failure'
        )
        """,
        {"run_id": mock_run_failed},
    )

    # 3. Build pipeline health summary
    checked_at = pendulum.now("UTC").to_iso8601_string()
    count = build_pipeline_health_summary(
        health_run_id=health_run_id,
        batch_id=health_run_id,
        checked_at=checked_at,
    )
    assert count == len(get_monitored_pipelines())

    # 4. Check status values in database
    gbfs_row = fetch_one(
        """
        SELECT * FROM etl_metadata.pipeline_health_summary
        WHERE health_run_id = :health_run_id AND monitored_dag_id = 'gbfs_metadata_daily_dag'
        """,
        {"health_run_id": health_run_id},
    )
    assert gbfs_row is not None
    assert gbfs_row["latest_run_status"] == "success"
    assert gbfs_row["health_status"] == "HEALTHY"

    station_row = fetch_one(
        """
        SELECT * FROM etl_metadata.pipeline_health_summary
        WHERE health_run_id = :health_run_id AND monitored_dag_id = 'station_status_snapshot_dag'
        """,
        {"health_run_id": health_run_id},
    )
    assert station_row is not None
    assert station_row["latest_run_status"] == "failed"
    assert station_row["health_status"] == "FAILED"

    # 5. Execute health DQ checks (should pass structural checks and log WARNING for station_status_snapshot_dag failure without raising exception)
    run_pipeline_health_dq_checks(run_id=health_run_id, batch_id=health_run_id)

    # Verify DQ result logged for WARNING severity failed_pipeline check
    dq_failed_row = fetch_one(
        """
        SELECT * FROM etl_metadata.dq_results
        WHERE run_id = :run_id AND check_name = 'pipeline_health_summary_failed_pipeline'
        """,
        {"run_id": health_run_id},
    )
    assert dq_failed_row is not None
    assert dq_failed_row["status"] == "failed"
    assert dq_failed_row["severity"] == "WARNING"
    assert dq_failed_row["failed_count"] >= 1
