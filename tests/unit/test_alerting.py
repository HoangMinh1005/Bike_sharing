"""
Unit tests for Alerting and Telegram Notification module.
"""
import os
from unittest.mock import MagicMock, patch
import pytest

from src.alerts.alert_config import AlertConfig, get_alert_config
from src.alerts.alert_models import (
    AlertPayload,
    AlertSeverity,
    AlertStatus,
    AlertType,
    NotificationStatus,
)
from src.alerts.alert_writer import (
    record_alert,
    resolve_open_alerts,
    should_suppress_duplicate_alert,
    update_alert_notification_status,
)
from src.alerts.notifier import notify_alert
from src.alerts.telegram_client import (
    format_telegram_message,
    send_telegram_message,
)
from src.alerts.airflow_callbacks import (
    airflow_task_failure_callback,
    airflow_task_success_callback,
)
from src.common.db import fetch_one


def test_alert_config_defaults(monkeypatch):
    """Test default AlertConfig parsing when env vars are unset."""
    monkeypatch.delenv("ALERT_WEBHOOK_ENABLED", raising=False)
    monkeypatch.delenv("ALERT_WEBHOOK_PROVIDER", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    config = AlertConfig.from_env()
    assert config.webhook_enabled is False
    assert config.provider == "telegram"
    assert config.telegram_bot_token == ""
    assert config.telegram_chat_id == ""
    assert config.dedup_window_minutes == 60
    assert config.request_timeout_seconds == 10


def test_format_telegram_message():
    """Test format_telegram_message creates clear mobile-friendly message."""
    payload = AlertPayload(
        alert_type=AlertType.AIRFLOW_TASK_FAILURE,
        severity=AlertSeverity.ERROR,
        source="airflow",
        title="Airflow Task Failed",
        message="Task failed due to connection timeout",
        dag_id="hourly_mart_build_dag",
        task_id="build_hourly_mart",
        run_id="manual__2026-08-17T12:00:00+00:00",
        details={"exception": "ConnectionTimeout: 10s", "log_url": "http://localhost:8080/log"},
    )

    msg = format_telegram_message(payload)
    assert "🚨 Bike Sharing Pipeline Alert" in msg
    assert "Severity: ERROR" in msg
    assert "Type: AIRFLOW_TASK_FAILURE" in msg
    assert "DAG: hourly_mart_build_dag" in msg
    assert "Task: build_hourly_mart" in msg
    assert "Log: http://localhost:8080/log" in msg


def test_record_alert_database():
    """Test recording an alert into PostgreSQL etl_metadata.alert_events."""
    payload = AlertPayload(
        alert_type="TEST_ALERT",
        severity=AlertSeverity.WARNING,
        source="unit_test",
        title="Unit Test Alert",
        message="Test alert description",
        dag_id="test_dag",
        task_id="test_task",
        notification_status=NotificationStatus.DISABLED,
    )

    alert_id = record_alert(payload)
    assert alert_id is not None

    # Verify DB content
    row = fetch_one(
        "SELECT * FROM etl_metadata.alert_events WHERE alert_id = CAST(:alert_id AS uuid)",
        {"alert_id": alert_id},
    )
    assert row is not None
    assert row["alert_type"] == "TEST_ALERT"
    assert row["severity"] == "WARNING"
    assert row["status"] == "OPEN"
    assert row["notification_status"] == "DISABLED"


def test_notify_alert_disabled_webhook(monkeypatch):
    """Test notify_alert records to DB and does not invoke Telegram when disabled."""
    monkeypatch.setenv("ALERT_WEBHOOK_ENABLED", "false")

    payload = AlertPayload(
        alert_type="TEST_DISABLED_WEBHOOK",
        severity=AlertSeverity.INFO,
        source="unit_test",
        title="Disabled Webhook Test",
        message="Should not call Telegram",
    )

    with patch("src.alerts.notifier.send_telegram_message") as mock_send:
        alert_id = notify_alert(payload, check_dedup=False)
        assert alert_id is not None
        mock_send.assert_not_called()

    row = fetch_one(
        "SELECT notification_status FROM etl_metadata.alert_events WHERE alert_id = CAST(:alert_id AS uuid)",
        {"alert_id": alert_id},
    )
    assert row["notification_status"] == NotificationStatus.DISABLED


def test_notify_alert_missing_credentials(monkeypatch):
    """Test notify_alert handles missing Telegram credentials without crashing."""
    monkeypatch.setenv("ALERT_WEBHOOK_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")

    payload = AlertPayload(
        alert_type="TEST_MISSING_CREDS",
        severity=AlertSeverity.ERROR,
        source="unit_test",
        title="Missing Credentials Test",
        message="Missing bot token",
    )

    with patch("src.alerts.notifier.send_telegram_message") as mock_send:
        alert_id = notify_alert(payload, check_dedup=False)
        assert alert_id is not None
        mock_send.assert_not_called()

    row = fetch_one(
        "SELECT notification_status, notification_error FROM etl_metadata.alert_events WHERE alert_id = CAST(:alert_id AS uuid)",
        {"alert_id": alert_id},
    )
    assert row["notification_status"] == NotificationStatus.SKIPPED
    assert "Missing TELEGRAM_BOT_TOKEN" in row["notification_error"]


def test_notify_alert_telegram_api_failure(monkeypatch):
    """Test notify_alert catches Telegram API failure, logs error, and updates status."""
    monkeypatch.setenv("ALERT_WEBHOOK_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "mock_token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "mock_chat_id")

    payload = AlertPayload(
        alert_type="TEST_API_FAILURE",
        severity=AlertSeverity.CRITICAL,
        source="unit_test",
        title="Telegram Failure Test",
        message="Simulating network error",
    )

    with patch("src.alerts.notifier.send_telegram_message", side_effect=RuntimeError("Telegram 500 Network Error")):
        alert_id = notify_alert(payload, check_dedup=False)
        assert alert_id is not None

    row = fetch_one(
        "SELECT status, notification_status, notification_error FROM etl_metadata.alert_events WHERE alert_id = CAST(:alert_id AS uuid)",
        {"alert_id": alert_id},
    )
    assert row["status"] == AlertStatus.FAILED_TO_SEND
    assert row["notification_status"] == NotificationStatus.FAILED_TO_SEND
    assert "Telegram 500 Network Error" in row["notification_error"]


def test_deduplication_suppression():
    """Test duplicate alerts within window are suppressed."""
    unique_type = f"TEST_DEDUP_{os.getpid()}"
    payload = AlertPayload(
        alert_type=unique_type,
        severity=AlertSeverity.ERROR,
        source="unit_test",
        title="Initial Dedup Alert",
        message="First instance",
        dag_id="dedup_dag",
        task_id="dedup_task",
    )

    # First alert should be recorded as OPEN
    first_id = notify_alert(payload, check_dedup=True)
    assert first_id is not None

    # Immediate second alert of same type/dag/task should be marked SKIPPED by dedup
    payload2 = AlertPayload(
        alert_type=unique_type,
        severity=AlertSeverity.ERROR,
        source="unit_test",
        title="Second Dedup Alert",
        message="Second instance",
        dag_id="dedup_dag",
        task_id="dedup_task",
    )

    second_id = notify_alert(payload2, check_dedup=True)
    assert second_id is not None

    row2 = fetch_one(
        "SELECT notification_status, notification_error FROM etl_metadata.alert_events WHERE alert_id = CAST(:alert_id AS uuid)",
        {"alert_id": second_id},
    )
    assert row2["notification_status"] == NotificationStatus.SKIPPED
    assert "Suppressed duplicate alert" in row2["notification_error"]


def test_airflow_task_failure_callback():
    """Test Airflow task failure callback extracts context and dispatches alert."""
    mock_dag = MagicMock()
    mock_dag.dag_id = "test_callback_dag"
    mock_task = MagicMock()
    mock_task.task_id = "test_callback_task"
    mock_ti = MagicMock()
    mock_ti.log_url = "http://localhost:8080/log/test"
    mock_ti.try_number = 1

    context = {
        "dag": mock_dag,
        "task": mock_task,
        "task_instance": mock_ti,
        "run_id": "test_run_123",
        "exception": ValueError("Simulated DB connection failed"),
    }

    # Calling callback must not raise exception
    airflow_task_failure_callback(context)

    # Verify alert in DB
    row = fetch_one(
        """
        SELECT * FROM etl_metadata.alert_events
        WHERE dag_id = 'test_callback_dag' AND task_id = 'test_callback_task'
        ORDER BY created_at DESC LIMIT 1
        """
    )
    assert row is not None
    assert row["alert_type"] == AlertType.AIRFLOW_TASK_FAILURE
    assert row["severity"] == AlertSeverity.ERROR
    assert "Simulated DB connection failed" in row["message"]


def test_notify_alert_successful_delivery_keeps_status_open(monkeypatch):
    """Test successful Telegram send leaves alert status as OPEN so it stays active on Dashboard."""
    monkeypatch.setenv("ALERT_WEBHOOK_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "mock_token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "mock_chat_id")

    payload = AlertPayload(
        alert_type="TEST_SUCCESS_DELIVERY_KEEP_OPEN",
        severity=AlertSeverity.ERROR,
        source="unit_test",
        title="Successful Delivery Test",
        message="Should remain OPEN in status and SENT in notification_status",
    )

    with patch("src.alerts.notifier.send_telegram_message", return_value={"ok": True}):
        alert_id = notify_alert(payload, check_dedup=False)
        assert alert_id is not None

    row = fetch_one(
        "SELECT status, notification_status FROM etl_metadata.alert_events WHERE alert_id = CAST(:alert_id AS uuid)",
        {"alert_id": alert_id},
    )
    assert row["status"] == AlertStatus.OPEN
    assert row["notification_status"] == NotificationStatus.SENT


def test_resolve_open_alerts():
    """Test resolve_open_alerts marks active alerts as RESOLVED with resolved_at."""
    payload = AlertPayload(
        alert_type="TEST_RESOLVE_TARGET",
        severity=AlertSeverity.ERROR,
        source="unit_test",
        title="To be resolved",
        message="Simulating active alert to resolve",
        dag_id="resolve_test_dag",
        task_id="resolve_test_task",
    )
    alert_id = record_alert(payload)
    assert alert_id is not None

    # Resolve alerts for this dag and task
    resolved_count = resolve_open_alerts(
        dag_id="resolve_test_dag",
        task_id="resolve_test_task",
        alert_type="TEST_RESOLVE_TARGET",
    )
    assert resolved_count >= 1

    row = fetch_one(
        "SELECT status, resolved_at FROM etl_metadata.alert_events WHERE alert_id = CAST(:alert_id AS uuid)",
        {"alert_id": alert_id},
    )
    assert row["status"] == AlertStatus.RESOLVED
    assert row["resolved_at"] is not None


def test_airflow_task_success_callback():
    """Test Airflow task success callback auto-resolves active task failure alerts."""
    # First, simulate a failure alert for a task
    fail_payload = AlertPayload(
        alert_type=AlertType.AIRFLOW_TASK_FAILURE,
        severity=AlertSeverity.ERROR,
        source="airflow",
        title="Task Failed",
        message="DB connection error",
        dag_id="recovery_dag",
        task_id="recovery_task",
    )
    alert_id = record_alert(fail_payload)
    assert alert_id is not None

    # Verify it is initially OPEN
    row_before = fetch_one(
        "SELECT status FROM etl_metadata.alert_events WHERE alert_id = CAST(:alert_id AS uuid)",
        {"alert_id": alert_id},
    )
    assert row_before["status"] == AlertStatus.OPEN

    # Simulate next task run succeeding
    mock_dag = MagicMock()
    mock_dag.dag_id = "recovery_dag"
    mock_task = MagicMock()
    mock_task.task_id = "recovery_task"

    success_context = {
        "dag": mock_dag,
        "task": mock_task,
    }
    airflow_task_success_callback(success_context)

    # Verify alert is now RESOLVED
    row_after = fetch_one(
        "SELECT status, resolved_at FROM etl_metadata.alert_events WHERE alert_id = CAST(:alert_id AS uuid)",
        {"alert_id": alert_id},
    )
    assert row_after["status"] == AlertStatus.RESOLVED
    assert row_after["resolved_at"] is not None

