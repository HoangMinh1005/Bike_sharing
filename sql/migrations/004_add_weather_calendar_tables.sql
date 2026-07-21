-- 004_add_weather_calendar_tables.sql
-- Create raw and staging tables, constraints, and indexes for weather & calendar enrichment pipeline

-- 1. Raw layer table and indexes for Weather
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

CREATE INDEX IF NOT EXISTS idx_raw_weather_hourly_batch_id ON raw.weather_hourly(batch_id);
CREATE INDEX IF NOT EXISTS idx_raw_weather_hourly_weather_time ON raw.weather_hourly(weather_time);
CREATE INDEX IF NOT EXISTS idx_raw_weather_hourly_location_name ON raw.weather_hourly(location_name);
CREATE INDEX IF NOT EXISTS idx_raw_weather_hourly_fetched_at ON raw.weather_hourly(fetched_at);
CREATE INDEX IF NOT EXISTS idx_raw_weather_hourly_loc_time ON raw.weather_hourly(location_name, weather_time);

-- 2. Raw layer table and indexes for Calendar
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

CREATE INDEX IF NOT EXISTS idx_raw_calendar_batch_id ON raw.calendar(batch_id);
CREATE INDEX IF NOT EXISTS idx_raw_calendar_date ON raw.calendar(calendar_date);

-- 3. Staging layer table and indexes for Weather
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

CREATE INDEX IF NOT EXISTS idx_staging_weather_hourly_batch_id ON staging.weather_hourly(batch_id);

-- 4. Staging layer table and indexes for Calendar
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

CREATE INDEX IF NOT EXISTS idx_staging_calendar_batch_id ON staging.calendar(batch_id);
