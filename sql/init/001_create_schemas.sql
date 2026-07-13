-- 001_create_schemas.sql
-- Create system schemas for the medallion data warehouse architecture

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS mart;
CREATE SCHEMA IF NOT EXISTS etl_metadata;
