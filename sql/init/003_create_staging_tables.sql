-- 003_create_staging_tables.sql
-- Create staging tables for bike sharing metadata

CREATE TABLE IF NOT EXISTS staging.system_information (
    system_id VARCHAR(100) PRIMARY KEY,
    system_name TEXT,
    operator TEXT,
    timezone TEXT,
    url TEXT,
    source_batch_id VARCHAR(100),
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staging.regions (
    region_id VARCHAR(100) PRIMARY KEY,
    region_name TEXT NOT NULL,
    source_batch_id VARCHAR(100),
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staging.vehicle_types (
    vehicle_type_id VARCHAR(100) PRIMARY KEY,
    vehicle_type_name TEXT,
    form_factor TEXT,
    propulsion_type TEXT,
    max_range_meters NUMERIC NULL,
    source_batch_id VARCHAR(100),
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staging.stations (
    station_id VARCHAR(100) PRIMARY KEY,
    station_name TEXT NOT NULL,
    short_name TEXT NULL,
    latitude NUMERIC,
    longitude NUMERIC,
    region_id VARCHAR(100) NULL REFERENCES staging.regions(region_id) ON DELETE SET NULL,
    capacity INTEGER NULL,
    is_active BOOLEAN DEFAULT TRUE,
    source_batch_id VARCHAR(100),
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
