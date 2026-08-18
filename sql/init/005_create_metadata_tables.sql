-- 005_create_metadata_tables.sql
-- Create database schema tracking tables for Airflow execution status and data quality metrics

CREATE TABLE IF NOT EXISTS etl_metadata.pipeline_runs (
    run_id VARCHAR(100) PRIMARY KEY,
    dag_id VARCHAR(200) NOT NULL,
    task_name VARCHAR(200) NULL,
    status VARCHAR(50) NOT NULL,
    started_at TIMESTAMP NOT NULL,
    ended_at TIMESTAMP NULL,
    duration_seconds NUMERIC NULL,
    records_extracted INTEGER DEFAULT 0,
    records_loaded INTEGER DEFAULT 0,
    records_rejected INTEGER DEFAULT 0,
    error_message TEXT NULL
);

CREATE TABLE IF NOT EXISTS etl_metadata.watermarks (
    source_name VARCHAR(100) PRIMARY KEY,
    last_successful_value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS etl_metadata.dq_results (
    check_id BIGSERIAL PRIMARY KEY,
    run_id VARCHAR(100) NOT NULL,
    table_name VARCHAR(200) NOT NULL,
    check_name VARCHAR(200) NOT NULL,
    status VARCHAR(50) NOT NULL,
    failed_count INTEGER DEFAULT 0,
    severity VARCHAR(50) NOT NULL,
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    message TEXT NULL
);

CREATE TABLE IF NOT EXISTS etl_metadata.rejected_records (
    id BIGSERIAL PRIMARY KEY,
    run_id VARCHAR(100) NOT NULL,
    source_name VARCHAR(100) NOT NULL,
    table_name VARCHAR(200) NOT NULL,
    reason TEXT NOT NULL,
    raw_payload JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS etl_metadata.pipeline_health_summary (
    id BIGSERIAL PRIMARY KEY,
    health_run_id TEXT NOT NULL,
    batch_id TEXT NOT NULL,
    checked_at TIMESTAMP NOT NULL,

    monitored_dag_id TEXT NOT NULL,
    pipeline_type TEXT NOT NULL,
    expected_schedule TEXT,
    freshness_threshold_minutes INTEGER NOT NULL,

    latest_run_id TEXT,
    latest_run_status TEXT,
    latest_started_at TIMESTAMP,
    latest_finished_at TIMESTAMP,
    latest_duration_seconds NUMERIC,

    latest_records_extracted INTEGER,
    latest_records_loaded INTEGER,
    latest_records_rejected INTEGER,

    latest_success_run_id TEXT,
    latest_success_finished_at TIMESTAMP,

    watermark_source_name TEXT,
    watermark_value TEXT,
    watermark_updated_at TIMESTAMP,

    freshness_lag_minutes NUMERIC,

    dq_total_checks INTEGER DEFAULT 0,
    dq_failed_checks INTEGER DEFAULT 0,
    dq_warning_checks INTEGER DEFAULT 0,
    dq_critical_failed_checks INTEGER DEFAULT 0,

    rejected_record_count INTEGER DEFAULT 0,

    health_status TEXT NOT NULL,
    health_message TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_pipeline_health_run_dag
        UNIQUE (health_run_id, monitored_dag_id),

    CONSTRAINT ck_pipeline_health_status
        CHECK (health_status IN ('HEALTHY', 'WARNING', 'FAILED', 'STALE', 'UNKNOWN'))
);

CREATE INDEX IF NOT EXISTS idx_pipeline_health_checked_at
ON etl_metadata.pipeline_health_summary(checked_at);

CREATE INDEX IF NOT EXISTS idx_pipeline_health_dag
ON etl_metadata.pipeline_health_summary(monitored_dag_id);

CREATE INDEX IF NOT EXISTS idx_pipeline_health_status
ON etl_metadata.pipeline_health_summary(health_status);

CREATE INDEX IF NOT EXISTS idx_pipeline_health_latest_status
ON etl_metadata.pipeline_health_summary(latest_run_status);

CREATE INDEX IF NOT EXISTS idx_pipeline_health_watermark
ON etl_metadata.pipeline_health_summary(watermark_source_name);

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


