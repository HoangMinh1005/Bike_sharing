"""
Centralized alert notifier orchestrating recording, deduplication, and notification delivery.
"""
from typing import Optional
from src.alerts.alert_config import get_alert_config
from src.alerts.alert_models import (
    AlertPayload,
    AlertStatus,
    NotificationStatus,
)
from src.alerts.alert_writer import (
    record_alert,
    should_suppress_duplicate_alert,
    update_alert_notification_status,
)
from src.alerts.telegram_client import format_telegram_message, send_telegram_message
from src.common.logger import get_logger

logger = get_logger(__name__)


def notify_alert(payload: AlertPayload, check_dedup: bool = True) -> Optional[str]:
    """
    Central dispatch function for creating and sending an alert.

    Safety guarantee:
    - Never raises exceptions that could fail the calling pipeline/task.
    - If Telegram is disabled or credentials missing, records to DB with appropriate status.
    - If Telegram API fails, updates DB record with error details without crashing.
    """
    try:
        config = get_alert_config()

        # 1. Deduplication check
        if check_dedup and should_suppress_duplicate_alert(
            alert_type=payload.alert_type,
            dag_id=payload.dag_id,
            task_id=payload.task_id,
            window_minutes=config.dedup_window_minutes,
        ):
            logger.info(
                f"Suppressed duplicate alert: type={payload.alert_type}, dag={payload.dag_id}, task={payload.task_id}"
            )
            # Record as SKIPPED for full audit trail
            payload.status = AlertStatus.SKIPPED
            payload.notification_status = NotificationStatus.SKIPPED
            payload.notification_error = f"Suppressed duplicate alert within {config.dedup_window_minutes}m window."
            return record_alert(payload)

        # 2. Determine initial notification channel & status
        if not config.webhook_enabled:
            payload.status = AlertStatus.OPEN
            payload.notification_channel = None
            payload.notification_status = NotificationStatus.DISABLED
            payload.notification_error = "Webhook notification is disabled in environment (ALERT_WEBHOOK_ENABLED=false)."
            return record_alert(payload)

        if config.provider != "telegram":
            payload.status = AlertStatus.OPEN
            payload.notification_channel = config.provider
            payload.notification_status = NotificationStatus.SKIPPED
            payload.notification_error = f"Provider '{config.provider}' is not supported yet (only 'telegram' is supported)."
            return record_alert(payload)

        # 3. Check Telegram credentials
        payload.notification_channel = "telegram"
        if not config.telegram_bot_token or not config.telegram_chat_id:
            payload.status = AlertStatus.OPEN
            payload.notification_status = NotificationStatus.SKIPPED
            payload.notification_error = "Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID in environment configuration."
            logger.warning(
                f"Alert {payload.alert_type} could not be sent to Telegram: Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID"
            )
            return record_alert(payload)

        # 4. Insert alert to DB first
        payload.notification_status = NotificationStatus.SKIPPED  # temporary until sent
        alert_id = record_alert(payload)

        # 5. Attempt Telegram delivery
        try:
            message_text = format_telegram_message(payload)
            send_telegram_message(
                bot_token=config.telegram_bot_token,
                chat_id=config.telegram_chat_id,
                text=message_text,
                timeout_seconds=config.request_timeout_seconds,
            )

            if alert_id:
                update_alert_notification_status(
                    alert_id=alert_id,
                    status=AlertStatus.SENT,
                    notification_status=NotificationStatus.SENT,
                    notification_error=None,
                )
        except Exception as telegram_error:
            logger.error(f"Failed to deliver Telegram alert for alert_id={alert_id}: {telegram_error}")
            if alert_id:
                update_alert_notification_status(
                    alert_id=alert_id,
                    status=AlertStatus.FAILED_TO_SEND,
                    notification_status=NotificationStatus.FAILED_TO_SEND,
                    notification_error=str(telegram_error),
                )

        return alert_id

    except Exception as general_error:
        logger.error(f"Unexpected error inside notify_alert: {general_error}")
        return None
