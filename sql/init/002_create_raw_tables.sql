-- 002_create_raw_tables.sql
-- Create table for storing raw JSON payloads from GBFS feeds

CREATE TABLE IF NOT EXISTS raw.gbfs_feed_snapshots (
    id BIGSERIAL PRIMARY KEY,
    batch_id VARCHAR(100) NOT NULL,
    feed_name VARCHAR(100) NOT NULL,
    language VARCHAR(10) DEFAULT 'en',
    fetched_at TIMESTAMP NOT NULL,
    source_last_updated TIMESTAMP NULL,
    ttl INTEGER NULL,
    raw_payload JSONB NOT NULL,
    payload_hash VARCHAR(64) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
