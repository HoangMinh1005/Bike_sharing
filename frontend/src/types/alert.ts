export type AlertSeverity = 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';
export type AlertStatus = 'OPEN' | 'SENT' | 'FAILED_TO_SEND' | 'RESOLVED' | 'SKIPPED';
export type NotificationStatus = 'DISABLED' | 'SKIPPED' | 'SENT' | 'FAILED_TO_SEND';

export interface AlertEvent {
  alert_id: string;
  created_at: string;
  alert_type: string;
  severity: AlertSeverity;
  source: string;
  dag_id?: string | null;
  task_id?: string | null;
  run_id?: string | null;
  status: AlertStatus;
  title: string;
  message: string;
  details?: Record<string, any> | null;
  notification_channel?: string | null;
  notification_status?: NotificationStatus | null;
  notification_error?: string | null;
  resolved_at?: string | null;
}

export interface AlertStats {
  total_active: number;
  critical_count: number;
  error_count: number;
  warning_count: number;
  info_count: number;
  resolved_count?: number;
}
