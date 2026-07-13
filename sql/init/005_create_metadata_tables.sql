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
