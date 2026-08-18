"""
Database operations for recording, updating, and deduplicating alert events.
"""
import json
from typing import Any, Dict, Optional
from sqlalchemy import text
from src.common.db import execute_sql, fetch_one, get_engine
from src.common.logger import get_logger
from src.alerts.alert_models import AlertPayload, AlertStatus

logger = get_logger(__name__)


def should_suppress_duplicate_alert(
    alert_type: str,
    dag_id: Optional[str] = None,
    task_id: Optional[str] = None,
    window_minutes: int = 60,
) -> bool:
    """
    Check if an active/open alert of the same type, dag, and task was recorded
    within the deduplication window to avoid alert storms and notification spam.
    """
    try:
        query = """
            SELECT CAST(alert_id AS text) AS alert_id
            FROM etl_metadata.alert_events
            WHERE alert_type = :alert_type
              AND (CAST(:dag_id AS text) IS NULL OR dag_id = :dag_id)
              AND (CAST(:task_id AS text) IS NULL OR task_id = :task_id)
              AND status IN ('OPEN', 'SENT')
              AND created_at >= NOW() - (CAST(:window_minutes AS text) || ' minutes')::INTERVAL
            ORDER BY created_at DESC
            LIMIT 1
        """
        row = fetch_one(
            query,
            {
                "alert_type": alert_type,
                "dag_id": dag_id,
                "task_id": task_id,
                "window_minutes": str(max(1, window_minutes)),
            },
        )
        if row and row.get("alert_id"):
            logger.info(
                f"Alert suppressed (duplicate within {window_minutes}m window): "
                f"type={alert_type}, dag={dag_id}, task={task_id}, prior_alert_id={row['alert_id']}"
            )
            return True
        return False
    except Exception as e:
        logger.warning(f"Error checking duplicate alerts (defaulting to non-suppressed): {e}")
        return False


def record_alert(payload: AlertPayload) -> Optional[str]:
    """
    Insert a new alert event into etl_metadata.alert_events table.
    Returns the generated alert_id as string, or None if insertion fails.
    """
    try:
        query = """
            INSERT INTO etl_metadata.alert_events (
                alert_type,
                severity,
                source,
                dag_id,
                task_id,
                run_id,
                status,
                title,
                message,
                details,
                notification_channel,
                notification_status,
                notification_error
            )
            VALUES (
                :alert_type,
                :severity,
                :source,
                :dag_id,
                :task_id,
                :run_id,
                :status,
                :title,
                :message,
                CAST(:details AS jsonb),
                :notification_channel,
                :notification_status,
                :notification_error
            )
            RETURNING CAST(alert_id AS text) AS alert_id
        """
        params = {
            "alert_type": payload.alert_type,
            "severity": payload.severity,
            "source": payload.source,
            "dag_id": payload.dag_id,
            "task_id": payload.task_id,
            "run_id": payload.run_id,
            "status": payload.status or AlertStatus.OPEN,
            "title": payload.title,
            "message": payload.message,
            "details": json.dumps(payload.details or {}),
            "notification_channel": payload.notification_channel,
            "notification_status": payload.notification_status,
            "notification_error": payload.notification_error,
        }

        engine = get_engine()
        with engine.begin() as conn:
            result = conn.execute(text(query), params)
            row = result.mappings().first()
            if row and row.get("alert_id"):
                alert_id = str(row["alert_id"])
                logger.info(f"Recorded alert event alert_id={alert_id} type={payload.alert_type} severity={payload.severity}")
                return alert_id
        return None
    except Exception as e:
        logger.error(f"Failed to record alert event to database: {e}")
        return None


def update_alert_notification_status(
    alert_id: str,
    status: str,
    notification_status: str,
    notification_error: Optional[str] = None,
) -> None:
    """
    Update the status and notification status of an existing alert.
    """
    try:
        query = """
            UPDATE etl_metadata.alert_events
            SET status = :status,
                notification_status = :notification_status,
                notification_error = :notification_error
            WHERE alert_id = CAST(:alert_id AS uuid)
        """
        execute_sql(
            query,
            {
                "alert_id": alert_id,
                "status": status,
                "notification_status": notification_status,
                "notification_error": notification_error,
            },
        )
    except Exception as e:
        logger.error(f"Failed to update alert notification status for alert_id={alert_id}: {e}")
