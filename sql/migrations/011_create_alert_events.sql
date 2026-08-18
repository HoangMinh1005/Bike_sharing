-- 011_create_alert_events.sql
-- Migration: Create centralized alerting events table for tracking Airflow task failures and pipeline health alerts

CREATE TABLE IF NOT EXISTS etl_metadata.alert_events (
    alert_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    source TEXT NOT NULL,
    dag_id TEXT NULL,
    task_id TEXT NULL,
    run_id TEXT NULL,
    status TEXT NOT NULL DEFAULT 'OPEN',
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    details JSONB NULL,
    notification_channel TEXT NULL,
    notification_status TEXT NULL,
    notification_error TEXT NULL,
    resolved_at TIMESTAMPTZ NULL,

    CONSTRAINT ck_alert_severity
        CHECK (severity IN ('INFO', 'WARNING', 'ERROR', 'CRITICAL')),

    CONSTRAINT ck_alert_status
        CHECK (status IN ('OPEN', 'SENT', 'FAILED_TO_SEND', 'RESOLVED', 'SKIPPED')),

    CONSTRAINT ck_alert_notification_status
        CHECK (notification_status IN ('DISABLED', 'SKIPPED', 'SENT', 'FAILED_TO_SEND'))
);

CREATE INDEX IF NOT EXISTS idx_alert_events_created_at
ON etl_metadata.alert_events(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_alert_events_severity
ON etl_metadata.alert_events(severity);

CREATE INDEX IF NOT EXISTS idx_alert_events_status
ON etl_metadata.alert_events(status);

CREATE INDEX IF NOT EXISTS idx_alert_events_dag_id
ON etl_metadata.alert_events(dag_id);

CREATE INDEX IF NOT EXISTS idx_alert_events_alert_type
ON etl_metadata.alert_events(alert_type);

CREATE INDEX IF NOT EXISTS idx_alert_events_notification_status
ON etl_metadata.alert_events(notification_status);
