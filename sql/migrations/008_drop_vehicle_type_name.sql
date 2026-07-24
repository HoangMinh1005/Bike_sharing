-- 008_drop_vehicle_type_name.sql
-- Migration script: Drop vehicle_type_name column from staging.vehicle_types and mart.vehicle_type_availability_summary

ALTER TABLE staging.vehicle_types DROP COLUMN IF EXISTS vehicle_type_name;
ALTER TABLE mart.vehicle_type_availability_summary DROP COLUMN IF EXISTS vehicle_type_name;
