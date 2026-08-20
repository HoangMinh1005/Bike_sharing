import React, { useState } from 'react';
import {
  Bell,
  AlertTriangle,
  CheckCircle2,
  ShieldAlert,
  AlertOctagon,
  Info,
  Send,
  Clock,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { useActiveAlerts, useAlertStats } from '../../hooks/useAlerts';
import { AlertEvent } from '../../types/alert';
import { formatDateTime } from '../../utils/format';

interface ActiveAlertsPanelProps {
  className?: string;
  defaultExpanded?: boolean;
}

export const ActiveAlertsPanel: React.FC<ActiveAlertsPanelProps> = ({
  className = '',
  defaultExpanded = false,
}) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const { data: statsRes, isLoading: isStatsLoading } = useAlertStats();
  const { data: alertsRes, isLoading: isAlertsLoading, isError, refetch } = useActiveAlerts(20);

  const stats = statsRes?.data || {
    total_active: 0,
    critical_count: 0,
    error_count: 0,
    warning_count: 0,
    info_count: 0,
    resolved_count: 0,
  };

  const alerts = alertsRes?.data || [];

  const getSeverityBadge = (severity: string, status?: string) => {
    if (status === 'RESOLVED') {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">
          <CheckCircle2 className="w-3 h-3" /> RESOLVED
        </span>
      );
    }
    switch (severity.toUpperCase()) {
      case 'CRITICAL':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-100 text-rose-800 border border-rose-200">
            <AlertOctagon className="w-3 h-3" /> CRITICAL
          </span>
        );
      case 'ERROR':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-50 text-red-700 border border-red-200">
            <ShieldAlert className="w-3 h-3" /> ERROR
          </span>
        );
      case 'WARNING':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
            <AlertTriangle className="w-3 h-3" /> WARNING
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
            <Info className="w-3 h-3" /> INFO
          </span>
        );
    }
  };

  const getNotificationBadge = (status?: string | null, channel?: string | null) => {
    if (!status || status === 'DISABLED') {
      return (
        <span className="text-[11px] font-medium text-slate-400">
          Webhook: Off
        </span>
      );
    }
    if (status === 'SENT') {
      return (
        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-600">
          <Send className="w-2.5 h-2.5" /> {channel || 'Telegram'}: Sent
        </span>
      );
    }
    if (status === 'FAILED_TO_SEND') {
      return (
        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-rose-600">
          <Send className="w-2.5 h-2.5" /> {channel || 'Telegram'}: Failed
        </span>
      );
    }
    return (
      <span className="text-[11px] font-medium text-slate-400">
        {status}
      </span>
    );
  };

  return (
    <div className={`bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden transition-all ${className}`}>
      {/* Clickable Header for Collapsible Toggle */}
      <div
        onClick={() => setIsExpanded((prev) => !prev)}
        className="px-6 py-4 flex flex-wrap items-center justify-between gap-3 bg-slate-50/70 hover:bg-slate-100/70 cursor-pointer select-none transition-colors"
      >
        <div className="flex items-center gap-2.5">
          <div className={`p-2 rounded-lg ${stats.total_active > 0 ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'}`}>
            <Bell className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-slate-900">Pipeline Alerts</h3>
              <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-slate-200/70 text-slate-600">
                {isExpanded ? 'Click to collapse' : 'Click to expand'}
              </span>
            </div>
            <p className="text-xs text-slate-500">Real-time task failures and resolved anomalies (retained 24h)</p>
          </div>
        </div>

        {/* Severity Summary Chips & Chevron Toggle */}
        <div className="flex items-center gap-2.5">
          {stats.critical_count > 0 && (
            <span className="px-2 py-0.5 rounded text-xs font-bold bg-rose-100 text-rose-700 border border-rose-200">
              {stats.critical_count} Critical
            </span>
          )}
          {stats.error_count > 0 && (
            <span className="px-2 py-0.5 rounded text-xs font-bold bg-red-100 text-red-700 border border-red-200">
              {stats.error_count} Errors
            </span>
          )}
          {stats.warning_count > 0 && (
            <span className="px-2 py-0.5 rounded text-xs font-bold bg-amber-100 text-amber-700 border border-amber-200">
              {stats.warning_count} Warnings
            </span>
          )}
          {(stats.resolved_count ?? 0) > 0 && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
              <CheckCircle2 className="w-3 h-3" /> {stats.resolved_count} Resolved (24h)
            </span>
          )}
          {stats.total_active === 0 && !isStatsLoading && (
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
              <CheckCircle2 className="w-3 h-3" /> All Active Normal
            </span>
          )}

          <div className="p-1 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-200/50 transition-colors ml-1">
            {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </div>
        </div>
      </div>

      {/* Expandable Body Content */}
      {isExpanded && (
        <div className="p-6 border-t border-slate-100">
          {isAlertsLoading ? (
            <div className="flex items-center justify-center py-8 text-xs text-slate-400">
              Loading pipeline alerts...
            </div>
          ) : isError ? (
            <div className="p-4 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-800 flex items-center justify-between">
              <span>Unable to load alerts at this moment.</span>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  refetch();
                }}
                className="font-semibold underline ml-2"
              >
                Retry
              </button>
            </div>
          ) : alerts.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <div className="w-10 h-10 rounded-full bg-emerald-50 flex items-center justify-center text-emerald-600 mb-2 border border-emerald-100">
                <CheckCircle2 className="w-5 h-5" />
              </div>
              <h4 className="text-sm font-semibold text-slate-800">No alerts in last 24 hours</h4>
              <p className="text-xs text-slate-500 max-w-md mt-0.5">
                The pipeline is operating normally with zero active issues and no recent errors in the last 24 hours.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-slate-100 -my-3">
              {alerts.map((alert: AlertEvent) => {
                const isResolved = alert.status === 'RESOLVED';
                return (
                  <div
                    key={alert.alert_id}
                    className={`py-3.5 first:pt-0 last:pb-0 ${isResolved ? 'opacity-90' : ''}`}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          {getSeverityBadge(alert.severity, alert.status)}
                          <span className={`text-xs font-bold ${isResolved ? 'text-slate-700' : 'text-slate-900'} truncate`}>
                            {alert.title}
                          </span>
                          {alert.dag_id && (
                            <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-600 text-[11px] font-mono">
                              {alert.dag_id}
                            </span>
                          )}
                          {alert.task_id && (
                            <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-500 text-[11px] font-mono">
                              {alert.task_id}
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-slate-600 break-words mt-0.5 leading-relaxed">
                          {alert.message}
                        </p>
                        {alert.notification_error && (
                          <p className="text-[11px] text-rose-500 mt-1 font-mono">
                            Note: {alert.notification_error}
                          </p>
                        )}
                      </div>

                      <div className="text-right shrink-0 flex flex-col items-end gap-1">
                        <span className="inline-flex items-center gap-1 text-[11px] text-slate-400">
                          <Clock className="w-3 h-3" /> {formatDateTime(alert.created_at)}
                        </span>
                        {isResolved ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
                            <CheckCircle2 className="w-2.5 h-2.5" />
                            {alert.resolved_at
                              ? `Fixed: ${formatDateTime(alert.resolved_at)}`
                              : 'Resolved'}
                          </span>
                        ) : (
                          getNotificationBadge(alert.notification_status, alert.notification_channel)
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ActiveAlertsPanel;
