-- 007_add_propulsion_type_to_mart.sql
-- Migration script: Ensure vehicle_type_name and propulsion_type exist in staging.vehicle_types and mart.vehicle_type_availability_summary

-- 1. Update staging.vehicle_types
ALTER TABLE staging.vehicle_types ADD COLUMN IF NOT EXISTS vehicle_type_name TEXT;
ALTER TABLE staging.vehicle_types ADD COLUMN IF NOT EXISTS propulsion_type TEXT;

-- 2. Update mart.vehicle_type_availability_summary
ALTER TABLE mart.vehicle_type_availability_summary ADD COLUMN IF NOT EXISTS vehicle_type_name TEXT;
ALTER TABLE mart.vehicle_type_availability_summary ADD COLUMN IF NOT EXISTS propulsion_type TEXT;
