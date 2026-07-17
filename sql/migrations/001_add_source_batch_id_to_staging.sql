-- 001_add_source_batch_id_to_staging.sql
-- Add source_batch_id to staging tables for lineage tracking

ALTER TABLE staging.system_information
ADD COLUMN IF NOT EXISTS source_batch_id VARCHAR(100);

ALTER TABLE staging.regions
ADD COLUMN IF NOT EXISTS source_batch_id VARCHAR(100);

ALTER TABLE staging.vehicle_types
ADD COLUMN IF NOT EXISTS source_batch_id VARCHAR(100);

ALTER TABLE staging.stations
ADD COLUMN IF NOT EXISTS source_batch_id VARCHAR(100);

-- Create indexes on source_batch_id for faster lookups
CREATE INDEX IF NOT EXISTS idx_system_information_source_batch_id
ON staging.system_information(source_batch_id);

CREATE INDEX IF NOT EXISTS idx_regions_source_batch_id
ON staging.regions(source_batch_id);

CREATE INDEX IF NOT EXISTS idx_vehicle_types_source_batch_id
ON staging.vehicle_types(source_batch_id);

CREATE INDEX IF NOT EXISTS idx_stations_source_batch_id
ON staging.stations(source_batch_id);
