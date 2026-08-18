"""
Manual test script for Centralized Alerting & Telegram Bot notification.
Usage:
    docker compose exec -T fastapi python scripts/test_alert.py
    or
    python scripts/test_alert.py (on host/VM)
"""
import sys
import os

# Ensure project root is in PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.alerts.alert_config import get_alert_config
from src.alerts.alert_models import AlertPayload, AlertSeverity, AlertType
from src.alerts.notifier import notify_alert


def run_test():
    config = get_alert_config()
    print("=" * 60)
    print("GBFS BIKE SHARING ALERT SYSTEM - MANUAL SMOKE TEST")
    print("=" * 60)
    print(f"Webhook Enabled : {config.webhook_enabled}")
    print(f"Provider        : {config.provider}")
    print(f"Telegram Token  : {'*' * 10 if config.telegram_bot_token else 'NOT SET'}")
    print(f"Telegram Chat ID: {config.telegram_chat_id or 'NOT SET'}")
    print(f"Dedup Window    : {config.dedup_window_minutes} mins")
    print("-" * 60)

    payload = AlertPayload(
        alert_type=AlertType.AIRFLOW_TASK_FAILURE,
        severity=AlertSeverity.ERROR,
        source="manual_smoke_test",
        title="Manual Test: Airflow Task Failure",
        message="Đây là cảnh báo thử nghiệm từ script test_alert.py. Hệ thống alerting và Telegram bot đang hoạt động chuẩn xác!",
        dag_id="hourly_mart_build_dag",
        task_id="build_hourly_station_availability_task",
        run_id="smoke_test__manual_run",
        details={
            "exception": "SimulatedException: Test connection timeout on mart builder",
            "log_url": "http://localhost:8080/dags/hourly_mart_build_dag/grid",
        },
    )

    print("Dispatching alert...")
    alert_id = notify_alert(payload, check_dedup=False)

    if alert_id:
        print(f"✅ Alert recorded to Database! Alert ID: {alert_id}")
        if config.webhook_enabled and config.telegram_bot_token and config.telegram_chat_id:
            print("🚀 Telegram message dispatched to group!")
        else:
            print("ℹ️ Telegram notification skipped (webhook disabled or credentials missing).")
    else:
        print("❌ Failed to create alert.")
    print("=" * 60)


if __name__ == "__main__":
    run_test()
