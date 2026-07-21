-- 002_add_station_status_tables.sql
-- Create raw and staging tables for station status snapshot pipeline

-- 1. Raw layer table and indexes
CREATE TABLE IF NOT EXISTS raw.station_status_snapshots (
    id BIGSERIAL PRIMARY KEY,
    batch_id VARCHAR(100) NOT NULL,
    run_id VARCHAR(100) NOT NULL,
    feed_name VARCHAR(100) DEFAULT 'station_status',
    language VARCHAR(10) DEFAULT 'en',
    fetched_at TIMESTAMP NOT NULL,
    source_last_updated TIMESTAMP NOT NULL,
    ttl INTEGER,
    station_id VARCHAR(100) NOT NULL,
    raw_station_status JSONB NOT NULL,
    payload_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_station_status_snapshot UNIQUE (batch_id, station_id, source_last_updated)
);

CREATE INDEX IF NOT EXISTS idx_station_status_snapshots_batch_id ON raw.station_status_snapshots(batch_id);
CREATE INDEX IF NOT EXISTS idx_station_status_snapshots_station_id ON raw.station_status_snapshots(station_id);
CREATE INDEX IF NOT EXISTS idx_station_status_snapshots_fetched_at ON raw.station_status_snapshots(fetched_at);
CREATE INDEX IF NOT EXISTS idx_station_status_snapshots_source_last_updated ON raw.station_status_snapshots(source_last_updated);
CREATE INDEX IF NOT EXISTS idx_station_status_snapshots_station_updated ON raw.station_status_snapshots(station_id, source_last_updated);

-- 2. Staging layer table for station status
CREATE TABLE IF NOT EXISTS staging.station_status (
    station_id VARCHAR(100) PRIMARY KEY,
    num_bikes_available INTEGER NOT NULL,
    num_docks_available INTEGER NOT NULL,
    num_bikes_disabled INTEGER DEFAULT 0,
    num_docks_disabled INTEGER DEFAULT 0,
    is_installed BOOLEAN DEFAULT TRUE,
    is_renting BOOLEAN DEFAULT TRUE,
    is_returning BOOLEAN DEFAULT TRUE,
    last_reported TIMESTAMP NOT NULL,
    source_last_updated TIMESTAMP NOT NULL,
    fetched_at TIMESTAMP NOT NULL,
    batch_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_station_status_batch_id ON staging.station_status(batch_id);

-- 3. Staging layer table for nested vehicle type counts
CREATE TABLE IF NOT EXISTS staging.station_vehicle_type_status (
    station_id VARCHAR(100) NOT NULL,
    vehicle_type_id VARCHAR(100) NOT NULL,
    count INTEGER NOT NULL,
    batch_id VARCHAR(100) NOT NULL,
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (station_id, vehicle_type_id)
);

CREATE INDEX IF NOT EXISTS idx_station_vehicle_type_status_batch_id ON staging.station_vehicle_type_status(batch_id);
