"""
Centralized Alerting Module.
"""
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

__all__ = [
    "AlertConfig",
    "get_alert_config",
    "AlertPayload",
    "AlertSeverity",
    "AlertStatus",
    "AlertType",
    "NotificationStatus",
    "record_alert",
    "resolve_open_alerts",
    "should_suppress_duplicate_alert",
    "update_alert_notification_status",
    "notify_alert",
    "format_telegram_message",
    "send_telegram_message",
    "airflow_task_failure_callback",
    "airflow_task_success_callback",
]
