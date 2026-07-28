-- 010_add_pipeline_health_summary_table.sql
-- Create table etl_metadata.pipeline_health_summary for monitoring ETL pipeline status and DQ health

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
