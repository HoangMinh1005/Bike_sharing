-- 005_add_hourly_mart_tables.sql
-- Migration script to create all 4 hourly mart tables, unique constraints, and indexes

CREATE SCHEMA IF NOT EXISTS mart;

-- 1. Hourly Station Availability Mart
CREATE TABLE IF NOT EXISTS mart.hourly_station_availability (
    id BIGSERIAL PRIMARY KEY,
    hour_bucket TIMESTAMP NOT NULL,
    station_id VARCHAR(100) NOT NULL,
    station_name TEXT,
    region_id VARCHAR(100),
    region_name TEXT,
    latitude NUMERIC,
    longitude NUMERIC,
    capacity INTEGER,
    observation_count INTEGER DEFAULT 0,
    avg_bikes_available NUMERIC,
    avg_docks_available NUMERIC,
    avg_bikes_disabled NUMERIC,
    avg_docks_disabled NUMERIC,
    min_bikes_available INTEGER,
    max_bikes_available INTEGER,
    empty_observation_count INTEGER DEFAULT 0,
    full_observation_count INTEGER DEFAULT 0,
    availability_rate NUMERIC,
    dock_utilization_rate NUMERIC,
    is_installed BOOLEAN DEFAULT TRUE,
    is_renting BOOLEAN DEFAULT TRUE,
    is_returning BOOLEAN DEFAULT TRUE,
    temperature NUMERIC,
    humidity NUMERIC,
    precipitation NUMERIC,
    wind_speed NUMERIC,
    weather_code INTEGER,
    calendar_date DATE,
    day_of_week VARCHAR(20),
    is_weekend BOOLEAN,
    is_holiday BOOLEAN,
    holiday_name VARCHAR(200),
    batch_id VARCHAR(100),
    run_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_hourly_station_avail UNIQUE (hour_bucket, station_id)
);

CREATE INDEX IF NOT EXISTS idx_mart_hsa_hour_bucket ON mart.hourly_station_availability(hour_bucket);
CREATE INDEX IF NOT EXISTS idx_mart_hsa_station_id ON mart.hourly_station_availability(station_id);
CREATE INDEX IF NOT EXISTS idx_mart_hsa_region_id ON mart.hourly_station_availability(region_id);
CREATE INDEX IF NOT EXISTS idx_mart_hsa_is_weekend ON mart.hourly_station_availability(is_weekend);
CREATE INDEX IF NOT EXISTS idx_mart_hsa_is_holiday ON mart.hourly_station_availability(is_holiday);
CREATE INDEX IF NOT EXISTS idx_mart_hsa_weather_code ON mart.hourly_station_availability(weather_code);

-- 2. Hourly Region Availability Mart
CREATE TABLE IF NOT EXISTS mart.hourly_region_availability (
    id BIGSERIAL PRIMARY KEY,
    hour_bucket TIMESTAMP NOT NULL,
    region_id VARCHAR(100) NOT NULL,
    region_name TEXT,
    station_count INTEGER DEFAULT 0,
    active_station_count INTEGER DEFAULT 0,
    total_observation_count INTEGER DEFAULT 0,
    avg_bikes_available NUMERIC,
    avg_docks_available NUMERIC,
    total_bikes_available NUMERIC,
    total_docks_available NUMERIC,
    avg_availability_rate NUMERIC,
    avg_dock_utilization_rate NUMERIC,
    empty_station_count INTEGER DEFAULT 0,
    full_station_count INTEGER DEFAULT 0,
    temperature NUMERIC,
    humidity NUMERIC,
    precipitation NUMERIC,
    wind_speed NUMERIC,
    weather_code INTEGER,
    calendar_date DATE,
    day_of_week VARCHAR(20),
    is_weekend BOOLEAN,
    is_holiday BOOLEAN,
    batch_id VARCHAR(100),
    run_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_hourly_region_avail UNIQUE (hour_bucket, region_id)
);

CREATE INDEX IF NOT EXISTS idx_mart_hra_hour_bucket ON mart.hourly_region_availability(hour_bucket);
CREATE INDEX IF NOT EXISTS idx_mart_hra_region_id ON mart.hourly_region_availability(region_id);

-- 3. Vehicle Type Availability Summary Mart
CREATE TABLE IF NOT EXISTS mart.vehicle_type_availability_summary (
    id BIGSERIAL PRIMARY KEY,
    hour_bucket TIMESTAMP NOT NULL,
    vehicle_type_id VARCHAR(100) NOT NULL,
    vehicle_type_form_factor TEXT,
    propulsion_type TEXT,
    station_count INTEGER DEFAULT 0,
    total_vehicle_count NUMERIC,
    avg_vehicle_count_per_station NUMERIC,
    min_vehicle_count INTEGER,
    max_vehicle_count INTEGER,
    batch_id VARCHAR(100),
    run_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_vehicle_type_summary UNIQUE (hour_bucket, vehicle_type_id)
);

CREATE INDEX IF NOT EXISTS idx_mart_vtas_hour_bucket ON mart.vehicle_type_availability_summary(hour_bucket);
CREATE INDEX IF NOT EXISTS idx_mart_vtas_vehicle_type_id ON mart.vehicle_type_availability_summary(vehicle_type_id);

-- 4. Weather Mobility Summary Mart
CREATE TABLE IF NOT EXISTS mart.weather_mobility_summary (
    id BIGSERIAL PRIMARY KEY,
    hour_bucket TIMESTAMP NOT NULL,
    station_count INTEGER DEFAULT 0,
    active_station_count INTEGER DEFAULT 0,
    total_bikes_available NUMERIC,
    total_docks_available NUMERIC,
    avg_availability_rate NUMERIC,
    avg_dock_utilization_rate NUMERIC,
    empty_station_count INTEGER DEFAULT 0,
    full_station_count INTEGER DEFAULT 0,
    temperature NUMERIC,
    humidity NUMERIC,
    precipitation NUMERIC,
    wind_speed NUMERIC,
    weather_code INTEGER,
    calendar_date DATE,
    day_of_week VARCHAR(20),
    is_weekend BOOLEAN,
    is_holiday BOOLEAN,
    holiday_name VARCHAR(200),
    batch_id VARCHAR(100),
    run_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_weather_mobility_summary UNIQUE (hour_bucket)
);

CREATE INDEX IF NOT EXISTS idx_mart_wms_hour_bucket ON mart.weather_mobility_summary(hour_bucket);
CREATE INDEX IF NOT EXISTS idx_mart_wms_weather_code ON mart.weather_mobility_summary(weather_code);
CREATE INDEX IF NOT EXISTS idx_mart_wms_is_weekend ON mart.weather_mobility_summary(is_weekend);
CREATE INDEX IF NOT EXISTS idx_mart_wms_is_holiday ON mart.weather_mobility_summary(is_holiday);
