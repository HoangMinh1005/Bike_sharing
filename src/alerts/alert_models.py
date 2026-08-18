"""
Data models and constants for the Alerting system.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


class AlertSeverity:
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AlertStatus:
    OPEN = "OPEN"
    SENT = "SENT"
    FAILED_TO_SEND = "FAILED_TO_SEND"
    RESOLVED = "RESOLVED"
    SKIPPED = "SKIPPED"


class NotificationStatus:
    DISABLED = "DISABLED"
    SKIPPED = "SKIPPED"
    SENT = "SENT"
    FAILED_TO_SEND = "FAILED_TO_SEND"


class AlertType:
    AIRFLOW_TASK_FAILURE = "AIRFLOW_TASK_FAILURE"
    PIPELINE_DAG_FAILED = "PIPELINE_DAG_FAILED"
    PIPELINE_DAG_STALE = "PIPELINE_DAG_STALE"
    DATA_FRESHNESS_STALE = "DATA_FRESHNESS_STALE"
    WEATHER_DATA_STALE = "WEATHER_DATA_STALE"
    HOURLY_MART_STALE = "HOURLY_MART_STALE"
    DAILY_SUMMARY_STALE = "DAILY_SUMMARY_STALE"
    DATA_QUALITY_CRITICAL = "DATA_QUALITY_CRITICAL"


@dataclass
class AlertPayload:
    alert_type: str
    severity: str
    source: str
    title: str
    message: str
    dag_id: Optional[str] = None
    task_id: Optional[str] = None
    run_id: Optional[str] = None
    status: str = AlertStatus.OPEN
    details: Optional[Dict[str, Any]] = field(default_factory=dict)
    notification_channel: Optional[str] = None
    notification_status: Optional[str] = None
    notification_error: Optional[str] = None
