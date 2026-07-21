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

CREATE TABLE IF NOT EXISTS raw.weather_hourly (
    id BIGSERIAL PRIMARY KEY,
    batch_id VARCHAR(100) NOT NULL,
    run_id VARCHAR(100) NOT NULL,
    source_name VARCHAR(100) DEFAULT 'open_meteo',
    location_name VARCHAR(100) NOT NULL,
    latitude NUMERIC NOT NULL,
    longitude NUMERIC NOT NULL,
    weather_time TIMESTAMP NOT NULL,
    fetched_at TIMESTAMP NOT NULL,
    raw_weather JSONB NOT NULL,
    payload_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_weather_hourly UNIQUE (batch_id, location_name, weather_time)
);

CREATE TABLE IF NOT EXISTS raw.calendar (
    id BIGSERIAL PRIMARY KEY,
    batch_id VARCHAR(100) NOT NULL,
    run_id VARCHAR(100) NOT NULL,
    calendar_date DATE NOT NULL,
    raw_calendar JSONB NOT NULL,
    payload_hash VARCHAR(64) NOT NULL,
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_raw_calendar UNIQUE (batch_id, calendar_date)
);
