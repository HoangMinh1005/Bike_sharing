-- 009_add_daily_mart_tables.sql
-- Migration script: Create daily summary and ranking mart tables in mart schema

-- 1. Daily Station Summary Mart Table
CREATE TABLE IF NOT EXISTS mart.daily_station_summary (
    id BIGSERIAL PRIMARY KEY,
    summary_date DATE NOT NULL,
    station_id VARCHAR(100) NOT NULL,
    station_name TEXT,
    region_id VARCHAR(100),
    region_name TEXT,
    latitude NUMERIC,
    longitude NUMERIC,
    capacity INTEGER,
    active_hour_count INTEGER DEFAULT 0,
    total_observation_count BIGINT DEFAULT 0,
    avg_bikes_available NUMERIC,
    avg_docks_available NUMERIC,
    avg_bikes_disabled NUMERIC,
    avg_docks_disabled NUMERIC,
    min_bikes_available INTEGER,
    max_bikes_available INTEGER,
    empty_hour_count INTEGER DEFAULT 0,
    full_hour_count INTEGER DEFAULT 0,
    empty_observation_count BIGINT DEFAULT 0,
    full_observation_count BIGINT DEFAULT 0,
    avg_availability_rate NUMERIC,
    avg_dock_utilization_rate NUMERIC,
    low_availability_hour_count INTEGER DEFAULT 0,
    high_demand_hour_count INTEGER DEFAULT 0,
    is_weekend BOOLEAN,
    is_holiday BOOLEAN,
    holiday_name TEXT,
    avg_temperature NUMERIC,
    total_precipitation NUMERIC,
    avg_wind_speed NUMERIC,
    batch_id VARCHAR(100),
    run_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_daily_station_summary UNIQUE(summary_date, station_id)
);

CREATE INDEX IF NOT EXISTS idx_mart_dss_summary_date ON mart.daily_station_summary(summary_date);
CREATE INDEX IF NOT EXISTS idx_mart_dss_station_id ON mart.daily_station_summary(station_id);
CREATE INDEX IF NOT EXISTS idx_mart_dss_region_id ON mart.daily_station_summary(region_id);
CREATE INDEX IF NOT EXISTS idx_mart_dss_is_weekend ON mart.daily_station_summary(is_weekend);
CREATE INDEX IF NOT EXISTS idx_mart_dss_is_holiday ON mart.daily_station_summary(is_holiday);
CREATE INDEX IF NOT EXISTS idx_mart_dss_avg_availability_rate ON mart.daily_station_summary(avg_availability_rate);

-- 2. Daily Region Summary Mart Table
CREATE TABLE IF NOT EXISTS mart.daily_region_summary (
    id BIGSERIAL PRIMARY KEY,
    summary_date DATE NOT NULL,
    region_id VARCHAR(100) NOT NULL,
    region_name TEXT,
    station_count INTEGER DEFAULT 0,
    active_station_count INTEGER DEFAULT 0,
    total_observation_count BIGINT DEFAULT 0,
    avg_bikes_available NUMERIC,
    avg_docks_available NUMERIC,
    total_bikes_available NUMERIC,
    total_docks_available NUMERIC,
    avg_availability_rate NUMERIC,
    avg_dock_utilization_rate NUMERIC,
    empty_station_count INTEGER DEFAULT 0,
    full_station_count INTEGER DEFAULT 0,
    low_availability_station_count INTEGER DEFAULT 0,
    high_demand_station_count INTEGER DEFAULT 0,
    is_weekend BOOLEAN,
    is_holiday BOOLEAN,
    holiday_name TEXT,
    avg_temperature NUMERIC,
    total_precipitation NUMERIC,
    avg_wind_speed NUMERIC,
    batch_id VARCHAR(100),
    run_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_daily_region_summary UNIQUE(summary_date, region_id)
);

CREATE INDEX IF NOT EXISTS idx_mart_drs_summary_date ON mart.daily_region_summary(summary_date);
CREATE INDEX IF NOT EXISTS idx_mart_drs_region_id ON mart.daily_region_summary(region_id);
CREATE INDEX IF NOT EXISTS idx_mart_drs_avg_availability_rate ON mart.daily_region_summary(avg_availability_rate);
CREATE INDEX IF NOT EXISTS idx_mart_drs_is_weekend ON mart.daily_region_summary(is_weekend);
CREATE INDEX IF NOT EXISTS idx_mart_drs_is_holiday ON mart.daily_region_summary(is_holiday);

-- 3. Station Demand Ranking Mart Table
CREATE TABLE IF NOT EXISTS mart.station_demand_ranking (
    id BIGSERIAL PRIMARY KEY,
    ranking_date DATE NOT NULL,
    station_id VARCHAR(100) NOT NULL,
    station_name TEXT,
    region_id VARCHAR(100),
    region_name TEXT,
    capacity INTEGER,
    active_hour_count INTEGER DEFAULT 0,
    total_observation_count BIGINT DEFAULT 0,
    avg_bikes_available NUMERIC,
    avg_docks_available NUMERIC,
    avg_availability_rate NUMERIC,
    avg_dock_utilization_rate NUMERIC,
    empty_hour_count INTEGER DEFAULT 0,
    full_hour_count INTEGER DEFAULT 0,
    low_availability_hour_count INTEGER DEFAULT 0,
    high_demand_hour_count INTEGER DEFAULT 0,
    demand_score NUMERIC,
    demand_rank INTEGER,
    demand_category VARCHAR(20),
    is_weekend BOOLEAN,
    is_holiday BOOLEAN,
    holiday_name TEXT,
    batch_id VARCHAR(100),
    run_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_station_demand_ranking UNIQUE(ranking_date, station_id)
);

CREATE INDEX IF NOT EXISTS idx_mart_sdr_ranking_date ON mart.station_demand_ranking(ranking_date);
CREATE INDEX IF NOT EXISTS idx_mart_sdr_station_id ON mart.station_demand_ranking(station_id);
CREATE INDEX IF NOT EXISTS idx_mart_sdr_region_id ON mart.station_demand_ranking(region_id);
CREATE INDEX IF NOT EXISTS idx_mart_sdr_demand_rank ON mart.station_demand_ranking(demand_rank);
CREATE INDEX IF NOT EXISTS idx_mart_sdr_demand_category ON mart.station_demand_ranking(demand_category);

-- 4. Daily System Summary Mart Table
CREATE TABLE IF NOT EXISTS mart.daily_system_summary (
    id BIGSERIAL PRIMARY KEY,
    summary_date DATE NOT NULL,
    station_count INTEGER DEFAULT 0,
    active_station_count INTEGER DEFAULT 0,
    region_count INTEGER DEFAULT 0,
    total_observation_count BIGINT DEFAULT 0,
    avg_bikes_available NUMERIC,
    avg_docks_available NUMERIC,
    total_bikes_available NUMERIC,
    total_docks_available NUMERIC,
    avg_availability_rate NUMERIC,
    avg_dock_utilization_rate NUMERIC,
    empty_station_count INTEGER DEFAULT 0,
    full_station_count INTEGER DEFAULT 0,
    low_availability_station_count INTEGER DEFAULT 0,
    high_demand_station_count INTEGER DEFAULT 0,
    avg_temperature NUMERIC,
    total_precipitation NUMERIC,
    avg_wind_speed NUMERIC,
    is_weekend BOOLEAN,
    is_holiday BOOLEAN,
    holiday_name TEXT,
    batch_id VARCHAR(100),
    run_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_daily_system_summary UNIQUE(summary_date)
);

CREATE INDEX IF NOT EXISTS idx_mart_dsys_summary_date ON mart.daily_system_summary(summary_date);
CREATE INDEX IF NOT EXISTS idx_mart_dsys_is_weekend ON mart.daily_system_summary(is_weekend);
CREATE INDEX IF NOT EXISTS idx_mart_dsys_is_holiday ON mart.daily_system_summary(is_holiday);
