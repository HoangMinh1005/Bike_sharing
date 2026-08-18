"""
Airflow callback handlers for task failures and pipeline exceptions.
"""
from typing import Any, Dict
from src.alerts.alert_models import AlertPayload, AlertSeverity, AlertType
from src.alerts.notifier import notify_alert
from src.common.logger import get_logger

logger = get_logger(__name__)


def airflow_task_failure_callback(context: Dict[str, Any]) -> None:
    """
    Airflow on_failure_callback handler.
    Extracts task failure context safely and dispatches an alert.
    Guaranteed not to raise exceptions.
    """
    try:
        dag_id = str(context.get("dag").dag_id if context.get("dag") else context.get("dag_id", "unknown_dag"))
        task_id = str(context.get("task").task_id if context.get("task") else context.get("task_id", "unknown_task"))
        run_id = str(context.get("run_id", "unknown_run"))

        # Extract exception or error details
        exception = context.get("exception")
        exception_str = str(exception) if exception else "Task execution failed without explicit exception message."

        # Extract log URL if available
        task_instance = context.get("task_instance") or context.get("ti")
        log_url = getattr(task_instance, "log_url", None)
        try_number = getattr(task_instance, "try_number", None)

        logical_date = context.get("logical_date") or context.get("execution_date")
        logical_date_str = str(logical_date) if logical_date else None

        title = f"Airflow Task Failed: {dag_id}.{task_id}"
        message = f"Task '{task_id}' in DAG '{dag_id}' failed: {exception_str}"

        details = {
            "exception": exception_str,
            "log_url": log_url,
            "try_number": try_number,
            "logical_date": logical_date_str,
            "run_id": run_id,
        }

        payload = AlertPayload(
            alert_type=AlertType.AIRFLOW_TASK_FAILURE,
            severity=AlertSeverity.ERROR,
            source="airflow",
            title=title,
            message=message,
            dag_id=dag_id,
            task_id=task_id,
            run_id=run_id,
            details=details,
        )

        logger.info(f"Triggering failure alert for DAG '{dag_id}', Task '{task_id}', Run ID '{run_id}'")
        notify_alert(payload, check_dedup=True)

    except Exception as e:
        logger.error(f"Error inside airflow_task_failure_callback: {e}")
