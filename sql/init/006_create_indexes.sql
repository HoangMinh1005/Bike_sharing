-- 006_create_indexes.sql
-- Create optimized database indexes for raw ingestion, staging, and metadata tables

-- raw.gbfs_feed_snapshots indexes
CREATE INDEX IF NOT EXISTS idx_gbfs_feed_snapshots_feed_name 
ON raw.gbfs_feed_snapshots (feed_name);

CREATE INDEX IF NOT EXISTS idx_gbfs_feed_snapshots_fetched_at 
ON raw.gbfs_feed_snapshots (fetched_at);

CREATE INDEX IF NOT EXISTS idx_gbfs_feed_snapshots_batch_id 
ON raw.gbfs_feed_snapshots (batch_id);

-- staging.stations indexes
CREATE INDEX IF NOT EXISTS idx_staging_stations_region_id 
ON staging.stations (region_id);

-- etl_metadata.pipeline_runs indexes
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_dag_id 
ON etl_metadata.pipeline_runs (dag_id);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status 
ON etl_metadata.pipeline_runs (status);

-- etl_metadata.dq_results indexes
CREATE INDEX IF NOT EXISTS idx_dq_results_run_id 
ON etl_metadata.dq_results (run_id);

CREATE INDEX IF NOT EXISTS idx_dq_results_table_name 
ON etl_metadata.dq_results (table_name);

-- etl_metadata.rejected_records indexes
CREATE INDEX IF NOT EXISTS idx_rejected_records_run_id 
ON etl_metadata.rejected_records (run_id);

CREATE INDEX IF NOT EXISTS idx_rejected_records_table_name 
ON etl_metadata.rejected_records (table_name);

-- staging.station_status & raw indexes for fast freshness check
CREATE INDEX IF NOT EXISTS idx_staging_station_status_fetched_at 
ON staging.station_status (fetched_at DESC);

CREATE INDEX IF NOT EXISTS idx_raw_station_status_snapshots_fetched_at 
ON raw.station_status_snapshots (fetched_at DESC);

-- etl_metadata.pipeline_runs partial composite index for fast freshness scan
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_dag_success 
ON etl_metadata.pipeline_runs (dag_id, started_at DESC) 
INCLUDE (ended_at) 
WHERE status = 'SUCCESS';

-- etl_metadata.pipeline_health_summary index for fast latest run lookup
CREATE INDEX IF NOT EXISTS idx_pipeline_health_checked_at 
ON etl_metadata.pipeline_health_summary (checked_at DESC);


