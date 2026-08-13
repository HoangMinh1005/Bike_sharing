import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_freshness_summary_endpoint():
    res = client.get("/api/v1/freshness/summary")
    assert res.status_code == 200
    json_data = res.json()
    assert "data" in json_data
    data = json_data["data"]

    # Verify top-level status
    assert "status" in data
    assert data["status"] in ("HEALTHY", "WARNING", "STALE", "UNKNOWN")
    assert "checked_at" in data

    # Verify component timestamp fields
    assert "latest_station_status_snapshot_at" in data
    assert "station_status_lag_minutes" in data
    assert "latest_hourly_mart_at" in data
    assert "hourly_mart_lag_minutes" in data
    assert "latest_daily_summary_date" in data
    assert "latest_pipeline_health_status" in data

    # Verify DAG runs breakdown list
    assert "latest_successful_dag_runs" in data
    assert isinstance(data["latest_successful_dag_runs"], list)
    for dag in data["latest_successful_dag_runs"]:
        assert "dag_id" in dag
        assert "status" in dag
        assert dag["status"] in ("HEALTHY", "WARNING", "STALE", "UNKNOWN")

    # Verify warnings list
    assert "warnings" in data
    assert isinstance(data["warnings"], list)
