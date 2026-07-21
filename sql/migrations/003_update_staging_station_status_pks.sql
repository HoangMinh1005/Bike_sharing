-- 003_update_staging_station_status_pks.sql
-- Alter staging.station_status and staging.station_vehicle_type_status tables
-- to include batch_id in their primary keys and support historical snapshots.

-- 1. Alter staging.station_status
ALTER TABLE staging.station_status DROP CONSTRAINT IF EXISTS station_status_pkey CASCADE;
ALTER TABLE staging.station_status ADD CONSTRAINT station_status_pkey PRIMARY KEY (station_id, batch_id);

-- 2. Alter staging.station_vehicle_type_status
ALTER TABLE staging.station_vehicle_type_status DROP CONSTRAINT IF EXISTS station_vehicle_type_status_pkey CASCADE;

-- Add new columns if they do not exist
ALTER TABLE staging.station_vehicle_type_status ADD COLUMN IF NOT EXISTS last_reported TIMESTAMP;
ALTER TABLE staging.station_vehicle_type_status ADD COLUMN IF NOT EXISTS source_last_updated TIMESTAMP;
ALTER TABLE staging.station_vehicle_type_status ADD COLUMN IF NOT EXISTS fetched_at TIMESTAMP;

-- Fill columns with fallback if there is existing data (just in case)
UPDATE staging.station_vehicle_type_status SET 
    last_reported = COALESCE(last_reported, loaded_at),
    source_last_updated = COALESCE(source_last_updated, loaded_at),
    fetched_at = COALESCE(fetched_at, loaded_at);

-- Alter columns to NOT NULL
ALTER TABLE staging.station_vehicle_type_status ALTER COLUMN last_reported SET NOT NULL;
ALTER TABLE staging.station_vehicle_type_status ALTER COLUMN source_last_updated SET NOT NULL;
ALTER TABLE staging.station_vehicle_type_status ALTER COLUMN fetched_at SET NOT NULL;

-- Add new primary key
ALTER TABLE staging.station_vehicle_type_status ADD CONSTRAINT station_vehicle_type_status_pkey PRIMARY KEY (station_id, vehicle_type_id, batch_id);
