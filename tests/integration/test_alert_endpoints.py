"""
Integration tests for FastAPI Alert endpoints.
"""
import pytest
from fastapi.testclient import TestClient

from api.main import app
from src.alerts.alert_models import AlertPayload, AlertSeverity, AlertType, NotificationStatus
from src.alerts.alert_writer import record_alert

client = TestClient(app)


@pytest.fixture(autouse=True)
def seed_test_alerts():
    """Seed test alert records into database before integration tests."""
    payload1 = AlertPayload(
        alert_type="INTEGRATION_TEST_CRITICAL",
        severity=AlertSeverity.CRITICAL,
        source="integration_test",
        title="Critical Integration Test Alert",
        message="Simulated critical failure",
        dag_id="int_test_dag_1",
        notification_status=NotificationStatus.DISABLED,
    )
    payload2 = AlertPayload(
        alert_type="INTEGRATION_TEST_WARNING",
        severity=AlertSeverity.WARNING,
        source="integration_test",
        title="Warning Integration Test Alert",
        message="Simulated warning condition",
        dag_id="int_test_dag_2",
        notification_status=NotificationStatus.DISABLED,
    )
    record_alert(payload1)
    record_alert(payload2)


def test_get_alerts_stats():
    """Test /api/v1/alerts/stats endpoint returns summary counts including resolved_count."""
    response = client.get("/api/v1/alerts/stats")
    assert response.status_code == 200
    data = response.json().get("data", {})
    assert "total_active" in data
    assert "critical_count" in data
    assert "error_count" in data
    assert "warning_count" in data
    assert "info_count" in data
    assert "resolved_count" in data
    assert data["critical_count"] >= 1
    assert data["warning_count"] >= 1


def test_get_latest_alerts():
    """Test /api/v1/alerts/latest endpoint returns array of alerts."""
    response = client.get("/api/v1/alerts/latest?limit=10")
    assert response.status_code == 200
    data = response.json().get("data", [])
    assert isinstance(data, list)
    assert len(data) >= 2
    assert "alert_id" in data[0]
    assert "created_at" in data[0]
    assert "title" in data[0]
    assert "severity" in data[0]


def test_get_active_alerts():
    """Test /api/v1/alerts/active endpoint returns active/open alerts and recent resolved alerts."""
    response = client.get("/api/v1/alerts/active?limit=10")
    assert response.status_code == 200
    data = response.json().get("data", [])
    assert isinstance(data, list)
    for alert in data:
        assert alert["status"] in ("OPEN", "FAILED_TO_SEND", "DISABLED", "RESOLVED", "SENT")


def test_get_alert_history_filtering():
    """Test /api/v1/alerts/history endpoint with pagination and severity filter."""
    response = client.get("/api/v1/alerts/history?severity=CRITICAL&limit=5&offset=0")
    assert response.status_code == 200
    json_res = response.json()
    data = json_res.get("data", [])
    assert isinstance(data, list)
    for alert in data:
        assert alert["severity"] == "CRITICAL"
