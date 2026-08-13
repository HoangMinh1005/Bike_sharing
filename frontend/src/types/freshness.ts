export type FreshnessStatus = 'HEALTHY' | 'WARNING' | 'STALE' | 'UNKNOWN';

export interface DagRunFreshness {
  dag_id: string;
  latest_success_at: string | null;
  lag_minutes: number | null;
  status: FreshnessStatus;
}

export interface DataFreshnessSummary {
  status: FreshnessStatus;
  checked_at: string;
  latest_station_status_snapshot_at: string | null;
  station_status_lag_minutes: number | null;
  latest_hourly_mart_at: string | null;
  hourly_mart_lag_minutes: number | null;
  latest_daily_summary_date: string | null;
  latest_pipeline_health_status: string | null;
  latest_successful_dag_runs: DagRunFreshness[];
  warnings: string[];
}
