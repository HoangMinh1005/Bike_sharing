export type PipelineHealthStatus = 'HEALTHY' | 'WARNING' | 'FAILED' | 'STALE' | 'UNKNOWN';

export interface PipelineHealth {
  health_run_id: string;
  checked_at: string;
  monitored_dag_id: string;
  pipeline_type: string;
  expected_schedule?: string;
  freshness_threshold_minutes: number;
  latest_run_id?: string;
  latest_run_status?: string;
  latest_started_at?: string;
  latest_finished_at?: string;
  latest_duration_seconds?: number;
  latest_records_extracted?: number;
  latest_records_loaded?: number;
  latest_records_rejected?: number;
  latest_success_run_id?: string;
  latest_success_finished_at?: string;
  watermark_source_name?: string;
  watermark_value?: string;
  watermark_updated_at?: string;
  freshness_lag_minutes?: number;
  dq_total_checks: number;
  dq_failed_checks: number;
  dq_warning_checks: number;
  dq_critical_failed_checks: number;
  rejected_record_count: number;
  health_status: PipelineHealthStatus;
  health_message?: string;
}

export interface PipelineRun {
  run_id: string;
  dag_id: string;
  task_name?: string;
  status: string;
  started_at: string;
  ended_at?: string;
  duration_seconds?: number;
  records_extracted?: number;
  records_loaded?: number;
  records_rejected?: number;
  error_message?: string;
}
