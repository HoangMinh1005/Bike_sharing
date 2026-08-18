"""
Telegram Bot API client for sending alert messages.
"""
import requests
from datetime import datetime, timezone
from src.alerts.alert_models import AlertPayload, AlertSeverity
from src.common.logger import get_logger

logger = get_logger(__name__)


def format_telegram_message(payload: AlertPayload) -> str:
    """
    Format alert payload into a clean, mobile-friendly plain text message.
    """
    icon = "🚨" if payload.severity in (AlertSeverity.CRITICAL, AlertSeverity.ERROR) else "⚠️"
    header = f"{icon} Bike Sharing Pipeline Alert"

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines = [
        header,
        "",
        f"Severity: {payload.severity}",
        f"Type: {payload.alert_type}",
    ]

    if payload.dag_id:
        lines.append(f"DAG: {payload.dag_id}")
    if payload.task_id:
        lines.append(f"Task: {payload.task_id}")
    if payload.run_id:
        # Truncate long run IDs for readability
        run_display = payload.run_id if len(payload.run_id) <= 40 else payload.run_id[:37] + "..."
        lines.append(f"Run ID: {run_display}")

    lines.append(f"Time: {now_utc}")
    lines.append(f"Message: {payload.message}")

    if payload.details:
        log_url = payload.details.get("log_url")
        if log_url:
            lines.append(f"Log: {log_url}")
        exception = payload.details.get("exception")
        if exception and exception != payload.message:
            # Truncate exception if overly long
            exc_str = str(exception)
            if len(exc_str) > 300:
                exc_str = exc_str[:297] + "..."
            lines.append(f"Error Details: {exc_str}")

    return "\n".join(lines)


def send_telegram_message(
    bot_token: str,
    chat_id: str,
    text: str,
    timeout_seconds: int = 10,
) -> bool:
    """
    Send text message to Telegram Bot API.
    Raises exceptions internally to be handled by notifier.
    """
    if not bot_token or not chat_id:
        raise ValueError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID configuration.")

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }

    response = requests.post(
        url,
        json=payload,
        timeout=timeout_seconds,
    )

    if response.status_code != 200:
        error_msg = f"Telegram API error {response.status_code}: {response.text}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    data = response.json()
    if not data.get("ok"):
        error_msg = f"Telegram API returned not ok: {data}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    logger.info(f"Telegram alert successfully sent to chat_id={chat_id}")
    return True
