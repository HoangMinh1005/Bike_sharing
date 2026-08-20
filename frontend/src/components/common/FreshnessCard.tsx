import React, { useState } from 'react';
import {
  Clock,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  HelpCircle,
  Activity,
  Calendar,
  Zap,
  Layers,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { DataFreshnessSummary, FreshnessStatus } from '../../types/freshness';
import { formatDateTime, formatDate } from '../../utils/format';

interface FreshnessCardProps {
  data?: DataFreshnessSummary;
  isLoading?: boolean;
  isError?: boolean;
  onRefresh?: () => void;
  defaultExpanded?: boolean;
  className?: string;
}

const statusConfig: Record<
  FreshnessStatus,
  { label: string; bg: string; text: string; border: string; icon: React.FC<{ className?: string }> }
> = {
  HEALTHY: {
    label: 'Live (Healthy)',
    bg: 'bg-emerald-50',
    text: 'text-emerald-700',
    border: 'border-emerald-200',
    icon: CheckCircle2,
  },
  WARNING: {
    label: 'Lagging (Warning)',
    bg: 'bg-amber-50',
    text: 'text-amber-700',
    border: 'border-amber-200',
    icon: AlertTriangle,
  },
  STALE: {
    label: 'Delayed (Stale)',
    bg: 'bg-rose-50',
    text: 'text-rose-700',
    border: 'border-rose-200',
    icon: AlertCircle,
  },
  UNKNOWN: {
    label: 'Unknown',
    bg: 'bg-slate-50',
    text: 'text-slate-600',
    border: 'border-slate-200',
    icon: HelpCircle,
  },
};

export const FreshnessCard: React.FC<FreshnessCardProps> = ({
  data,
  isLoading,
  isError,
  onRefresh,
  defaultExpanded = false,
  className = '',
}) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  if (isLoading) {
    return (
      <div className={`bg-white rounded-xl border border-slate-200 px-5 py-3 shadow-xs animate-pulse mb-6 flex items-center justify-between ${className}`}>
        <div className="flex items-center gap-3 w-1/2">
          <div className="w-4 h-4 bg-slate-200 rounded-full" />
          <div className="h-4 bg-slate-200 rounded w-1/3" />
        </div>
        <div className="h-4 bg-slate-100 rounded w-20" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className={`bg-white rounded-xl border border-slate-200 px-5 py-3 shadow-xs mb-6 flex items-center justify-between ${className}`}>
        <div className="flex items-center gap-2.5">
          <AlertCircle className="w-4 h-4 text-amber-500" />
          <span className="text-xs font-bold text-slate-800">Data Freshness:</span>
          <span className="text-xs text-slate-500">Could not retrieve real-time metrics</span>
        </div>
        {onRefresh && (
          <button
            onClick={onRefresh}
            className="text-xs font-semibold px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors"
          >
            Retry
          </button>
        )}
      </div>
    );
  }

  const overallStatus = data.status || 'UNKNOWN';
  const conf = statusConfig[overallStatus] || statusConfig.UNKNOWN;
  const StatusIcon = conf.icon;

  const formatLag = (lag: number | null | undefined) => {
    if (lag === null || lag === undefined) return 'N/A';
    if (lag < 1) return '< 1m';
    if (lag < 60) return `${Math.round(lag)}m lag`;
    const hours = (lag / 60).toFixed(1);
    return `${hours}h lag`;
  };

  return (
    <div className={`bg-white rounded-xl border border-slate-200 shadow-xs mb-6 overflow-hidden transition-all ${className}`}>
      {/* 1. Mini Compact Header Strip (Always Visible, takes minimal vertical space) */}
      <div
        onClick={() => setIsExpanded((prev) => !prev)}
        className="px-5 py-2.5 flex flex-wrap items-center justify-between gap-3 bg-slate-50/70 hover:bg-slate-100/70 cursor-pointer select-none transition-colors"
      >
        {/* Left: Freshness Status & Quick Pillar Summary */}
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-indigo-600" />
            <span className="text-xs font-bold text-slate-800">Data Freshness:</span>
            <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold ${conf.bg} ${conf.text} border ${conf.border}`}>
              <StatusIcon className="w-3 h-3" />
              {conf.label}
            </span>
          </div>

          {/* Quick Metrics (Visible on medium+ screens) */}
          <div className="hidden md:flex items-center gap-3 text-xs text-slate-600 pl-3 border-l border-slate-200">
            <span className="inline-flex items-center gap-1.5">
              <Zap className="w-3.5 h-3.5 text-emerald-600" />
              Station: <strong className="text-slate-700">{formatLag(data.station_status_lag_minutes)}</strong>
            </span>
            <span className="text-slate-300">•</span>
            <span className="inline-flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-indigo-600" />
              Hourly Mart: <strong className="text-slate-700">{formatLag(data.hourly_mart_lag_minutes)}</strong>
            </span>
            <span className="text-slate-300">•</span>
            <span className="inline-flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5 text-blue-600" />
              Daily: <strong className="text-slate-700">{data.latest_daily_summary_date ? formatDate(data.latest_daily_summary_date) : 'Pending'}</strong>
            </span>
          </div>
        </div>

        {/* Right: Last Checked Timestamp & Expand / Collapse Trigger */}
        <div className="flex items-center gap-3">
          <span className="text-[11px] text-slate-400 hidden sm:inline">
            Checked: <strong className="font-medium text-slate-600">{formatDateTime(data.checked_at)}</strong>
          </span>
          <div className="inline-flex items-center gap-1 text-[11px] font-semibold text-slate-600 px-2 py-1 rounded-md bg-slate-200/60 hover:bg-slate-200 transition-colors">
            {isExpanded ? 'Collapse' : 'Details'}
            {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </div>
        </div>
      </div>

      {/* 2. Expanded Detail Section (Dropdown on click) */}
      {isExpanded && (
        <div className="border-t border-slate-100 p-5 bg-white space-y-5">
          {/* 4 Core Pillars Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
            {/* Pillar 1: Station Status Snapshot */}
            <div className="p-3.5 rounded-lg border border-slate-100 bg-slate-50/50">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs font-semibold text-slate-500 flex items-center gap-1.5">
                  <Zap className="w-3.5 h-3.5 text-emerald-600" />
                  Station Status
                </span>
                <span
                  className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                    data.station_status_lag_minutes !== null && data.station_status_lag_minutes <= 30
                      ? 'bg-emerald-100 text-emerald-800'
                      : data.station_status_lag_minutes !== null && data.station_status_lag_minutes <= 60
                      ? 'bg-amber-100 text-amber-800'
                      : 'bg-rose-100 text-rose-800'
                  }`}
                >
                  {data.station_status_lag_minutes !== null && data.station_status_lag_minutes <= 30
                    ? 'LIVE'
                    : data.station_status_lag_minutes !== null && data.station_status_lag_minutes <= 60
                    ? 'LAG'
                    : 'STALE'}
                </span>
              </div>
              <p className="text-xs font-bold text-slate-800 truncate">
                {data.latest_station_status_snapshot_at ? formatDateTime(data.latest_station_status_snapshot_at) : 'Not available'}
              </p>
              <p className="text-[11px] text-slate-500 mt-0.5">Lag: {formatLag(data.station_status_lag_minutes)}</p>
            </div>

            {/* Pillar 2: Hourly Mart */}
            <div className="p-3.5 rounded-lg border border-slate-100 bg-slate-50/50">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs font-semibold text-slate-500 flex items-center gap-1.5">
                  <Layers className="w-3.5 h-3.5 text-indigo-600" />
                  Hourly Mart
                </span>
                <span
                  className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                    data.hourly_mart_lag_minutes !== null && data.hourly_mart_lag_minutes <= 90
                      ? 'bg-emerald-100 text-emerald-800'
                      : data.hourly_mart_lag_minutes !== null && data.hourly_mart_lag_minutes <= 180
                      ? 'bg-amber-100 text-amber-800'
                      : 'bg-rose-100 text-rose-800'
                  }`}
                >
                  {data.hourly_mart_lag_minutes !== null && data.hourly_mart_lag_minutes <= 90
                    ? 'UP-TO-DATE'
                    : data.hourly_mart_lag_minutes !== null && data.hourly_mart_lag_minutes <= 180
                    ? 'LAG'
                    : 'STALE'}
                </span>
              </div>
              <p className="text-xs font-bold text-slate-800 truncate">
                {data.latest_hourly_mart_at ? formatDateTime(data.latest_hourly_mart_at) : 'Not available'}
              </p>
              <p className="text-[11px] text-slate-500 mt-0.5">Lag: {formatLag(data.hourly_mart_lag_minutes)}</p>
            </div>

            {/* Pillar 3: Daily Summary */}
            <div className="p-3.5 rounded-lg border border-slate-100 bg-slate-50/50">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs font-semibold text-slate-500 flex items-center gap-1.5">
                  <Calendar className="w-3.5 h-3.5 text-blue-600" />
                  Daily Summary
                </span>
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-blue-100 text-blue-800">DAILY</span>
              </div>
              <p className="text-xs font-bold text-slate-800">
                {data.latest_daily_summary_date ? formatDate(data.latest_daily_summary_date) : 'Not available'}
              </p>
              <p className="text-[11px] text-slate-500 mt-0.5">Aggregated Mart Records</p>
            </div>

            {/* Pillar 4: Pipeline Health & DQ */}
            <div className="p-3.5 rounded-lg border border-slate-100 bg-slate-50/50">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs font-semibold text-slate-500 flex items-center gap-1.5">
                  <Activity className="w-3.5 h-3.5 text-purple-600" />
                  Health & DQ
                </span>
                <span
                  className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                    data.quality_status === 'HEALTHY' || data.latest_pipeline_health_status === 'HEALTHY'
                      ? 'bg-emerald-100 text-emerald-800'
                      : data.quality_status === 'WARNING' || data.latest_pipeline_health_status === 'WARNING'
                      ? 'bg-amber-100 text-amber-800'
                      : 'bg-rose-100 text-rose-800'
                  }`}
                >
                  {data.quality_status === 'WARNING'
                    ? 'DQ WARNING'
                    : data.latest_pipeline_health_status || data.quality_status || 'UNKNOWN'}
                </span>
              </div>
              <p className="text-xs font-bold text-slate-800 truncate">
                {data.latest_pipeline_health_status === 'WARNING'
                  ? 'Active with DQ Notices'
                  : data.latest_pipeline_health_status || 'Checking...'}
              </p>
              <p className="text-[11px] text-slate-500 mt-0.5">SLA Freshness & Quality</p>
            </div>
          </div>

          {/* DAG Success Run Mini-Grid */}
          {data.latest_successful_dag_runs && data.latest_successful_dag_runs.length > 0 && (
            <div className="border-t border-slate-100 pt-3.5">
              <h4 className="text-[11px] font-bold text-slate-500 mb-2 uppercase tracking-wider">Airflow Orchestration Runs</h4>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
                {data.latest_successful_dag_runs.map((dag) => (
                  <div key={dag.dag_id} className="p-2 rounded bg-slate-50 border border-slate-100 text-center">
                    <span
                      className={`inline-block w-1.5 h-1.5 rounded-full mb-0.5 ${
                        dag.status === 'HEALTHY'
                          ? 'bg-emerald-500'
                          : dag.status === 'WARNING'
                          ? 'bg-amber-500'
                          : dag.status === 'STALE'
                          ? 'bg-rose-500'
                          : 'bg-slate-400'
                      }`}
                    />
                    <p className="text-[11px] font-bold text-slate-700 truncate" title={dag.dag_id}>
                      {dag.dag_id.replace('_dag', '')}
                    </p>
                    <p className="text-[10px] text-slate-400">{formatLag(dag.lag_minutes)}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Warnings if any */}
          {data.warnings && data.warnings.length > 0 && (
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold mb-0.5">Freshness Notices:</p>
                <ul className="list-disc list-inside space-y-0.5 text-amber-700 text-[11px]">
                  {data.warnings.map((w, idx) => (
                    <li key={idx}>{w}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default FreshnessCard;
