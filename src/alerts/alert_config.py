"""
Alerting system configuration loaded from environment variables.
"""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AlertConfig:
    webhook_enabled: bool
    provider: str
    telegram_bot_token: str
    telegram_chat_id: str
    dedup_window_minutes: int
    request_timeout_seconds: int

    @classmethod
    def from_env(cls) -> "AlertConfig":
        enabled_raw = os.getenv("ALERT_WEBHOOK_ENABLED", "false").strip().lower()
        webhook_enabled = enabled_raw in ("true", "1", "yes", "on")

        provider = os.getenv("ALERT_WEBHOOK_PROVIDER", "telegram").strip().lower()
        telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

        try:
            dedup_window_minutes = int(os.getenv("ALERT_DEDUP_WINDOW_MINUTES", "60"))
        except ValueError:
            dedup_window_minutes = 60

        try:
            request_timeout_seconds = int(os.getenv("ALERT_REQUEST_TIMEOUT_SECONDS", "10"))
        except ValueError:
            request_timeout_seconds = 10

        return cls(
            webhook_enabled=webhook_enabled,
            provider=provider,
            telegram_bot_token=telegram_bot_token,
            telegram_chat_id=telegram_chat_id,
            dedup_window_minutes=dedup_window_minutes,
            request_timeout_seconds=request_timeout_seconds,
        )


def get_alert_config() -> AlertConfig:
    """Helper to get current alert configuration."""
    return AlertConfig.from_env()
