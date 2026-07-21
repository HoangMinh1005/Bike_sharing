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

CREATE TABLE IF NOT EXISTS staging.station_status (
    station_id VARCHAR(100) NOT NULL,
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
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (station_id, batch_id)
);

CREATE TABLE IF NOT EXISTS staging.station_vehicle_type_status (
    station_id VARCHAR(100) NOT NULL,
    vehicle_type_id VARCHAR(100) NOT NULL,
    count INTEGER NOT NULL,
    last_reported TIMESTAMP NOT NULL,
    source_last_updated TIMESTAMP NOT NULL,
    fetched_at TIMESTAMP NOT NULL,
    batch_id VARCHAR(100) NOT NULL,
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (station_id, vehicle_type_id, batch_id)
);

CREATE TABLE IF NOT EXISTS staging.weather_hourly (
    location_name VARCHAR(100) NOT NULL,
    latitude NUMERIC NOT NULL,
    longitude NUMERIC NOT NULL,
    weather_time TIMESTAMP NOT NULL,
    temperature NUMERIC,
    humidity NUMERIC,
    precipitation NUMERIC,
    wind_speed NUMERIC,
    weather_code INTEGER,
    fetched_at TIMESTAMP NOT NULL,
    batch_id VARCHAR(100) NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (location_name, weather_time, batch_id)
);

CREATE TABLE IF NOT EXISTS staging.calendar (
    calendar_date DATE NOT NULL,
    day_of_week VARCHAR(20) NOT NULL,
    is_weekend BOOLEAN NOT NULL,
    is_holiday BOOLEAN NOT NULL,
    holiday_name VARCHAR(200),
    batch_id VARCHAR(100) NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (calendar_date, batch_id)
);
