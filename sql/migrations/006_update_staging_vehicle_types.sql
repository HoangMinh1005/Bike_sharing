-- 006_update_staging_vehicle_types.sql
-- Migration script: replace vehicle_type_name with propulsion_type in staging.vehicle_types and mart.vehicle_type_availability_summary

-- 1. Update staging.vehicle_types
ALTER TABLE staging.vehicle_types DROP COLUMN IF EXISTS vehicle_type_name;
ALTER TABLE staging.vehicle_types ADD COLUMN IF NOT EXISTS propulsion_type TEXT;

-- 2. Update mart.vehicle_type_availability_summary
ALTER TABLE mart.vehicle_type_availability_summary DROP COLUMN IF EXISTS vehicle_type_name;
ALTER TABLE mart.vehicle_type_availability_summary ADD COLUMN IF NOT EXISTS propulsion_type TEXT;
