import React from 'react';
import { Clock, CheckCircle2, AlertTriangle, AlertCircle, HelpCircle, Activity, Calendar, Zap, Layers } from 'lucide-react';
import { DataFreshnessSummary, FreshnessStatus } from '../../types/freshness';
import { formatDateTime, formatDate } from '../../utils/format';

interface FreshnessCardProps {
  data?: DataFreshnessSummary;
  isLoading?: boolean;
  isError?: boolean;
  onRefresh?: () => void;
}

const statusConfig: Record<
  FreshnessStatus,
  { label: string; bg: string; text: string; border: string; icon: React.FC<{ className?: string }> }
> = {
  HEALTHY: {
    label: 'Healthy (Live)',
    bg: 'bg-emerald-50',
    text: 'text-emerald-700',
    border: 'border-emerald-200',
    icon: CheckCircle2,
  },
  WARNING: {
    label: 'Warning (Lagging)',
    bg: 'bg-amber-50',
    text: 'text-amber-700',
    border: 'border-amber-200',
    icon: AlertTriangle,
  },
  STALE: {
    label: 'Stale (Delayed)',
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

export const FreshnessCard: React.FC<FreshnessCardProps> = ({ data, isLoading, isError, onRefresh }) => {
  if (isLoading) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs animate-pulse mb-8">
        <div className="h-4 bg-slate-200 rounded w-1/4 mb-4"></div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="h-16 bg-slate-100 rounded"></div>
          <div className="h-16 bg-slate-100 rounded"></div>
          <div className="h-16 bg-slate-100 rounded"></div>
          <div className="h-16 bg-slate-100 rounded"></div>
        </div>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs mb-8 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-amber-500" />
          <div>
            <h3 className="text-sm font-bold text-slate-800">Data Freshness Not Available</h3>
            <p className="text-xs text-slate-500">Could not retrieve real-time data currency metrics from backend.</p>
          </div>
        </div>
        {onRefresh && (
          <button
            onClick={onRefresh}
            className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors"
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
    if (lag === null || lag === undefined) return 'Not available yet';
    if (lag < 1) return '< 1 min ago';
    if (lag < 60) return `${Math.round(lag)} min ago`;
    const hours = (lag / 60).toFixed(1);
    return `${hours} hrs ago`;
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-xs mb-8 overflow-hidden">
      {/* Top Banner */}
      <div className="px-6 py-4 border-b border-slate-100 flex flex-wrap items-center justify-between gap-3 bg-slate-50/50">
        <div className="flex items-center gap-2.5">
          <Clock className="w-4 h-4 text-indigo-600" />
          <h3 className="text-sm font-bold text-slate-800">Data Freshness & Currency</h3>
          <span className="text-xs text-slate-400">|</span>
          <span className="text-xs text-slate-500">
            Last Checked: <strong className="font-medium text-slate-700">{formatDateTime(data.checked_at)}</strong>
          </span>
        </div>

        {/* Overall Status Badge */}
        <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full border text-xs font-bold ${conf.bg} ${conf.text} ${conf.border}`}>
          <StatusIcon className="w-3.5 h-3.5" />
          <span>{conf.label}</span>
        </div>
      </div>

      {/* 4 Core Ingestion & Mart Pillars */}
      <div className="p-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* 1. Real-time Station Snapshot */}
        <div className="p-4 rounded-xl border border-slate-100 bg-slate-50/40 hover:bg-slate-50 transition-colors">
          <div className="flex items-center justify-between mb-2">
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
          <p className="text-sm font-bold text-slate-800 truncate">
            {data.latest_station_status_snapshot_at ? formatDateTime(data.latest_station_status_snapshot_at) : 'Not available yet'}
          </p>
          <p className="text-xs text-slate-500 mt-1">Lag: {formatLag(data.station_status_lag_minutes)}</p>
        </div>

        {/* 2. Hourly Mart */}
        <div className="p-4 rounded-xl border border-slate-100 bg-slate-50/40 hover:bg-slate-50 transition-colors">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-slate-500 flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-indigo-600" />
              Hourly Mart
            </span>
            <span
              className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                data.hourly_mart_lag_minutes !== null && data.hourly_mart_lag_minutes <= 120
                  ? 'bg-emerald-100 text-emerald-800'
                  : data.hourly_mart_lag_minutes !== null && data.hourly_mart_lag_minutes <= 240
                  ? 'bg-amber-100 text-amber-800'
                  : 'bg-rose-100 text-rose-800'
              }`}
            >
              {data.hourly_mart_lag_minutes !== null && data.hourly_mart_lag_minutes <= 120
                ? 'UP-TO-DATE'
                : data.hourly_mart_lag_minutes !== null && data.hourly_mart_lag_minutes <= 240
                ? 'LAG'
                : 'STALE'}
            </span>
          </div>
          <p className="text-sm font-bold text-slate-800 truncate">
            {data.latest_hourly_mart_at ? formatDateTime(data.latest_hourly_mart_at) : 'Not available yet'}
          </p>
          <p className="text-xs text-slate-500 mt-1">Lag: {formatLag(data.hourly_mart_lag_minutes)}</p>
        </div>

        {/* 3. Daily Summary Mart */}
        <div className="p-4 rounded-xl border border-slate-100 bg-slate-50/40 hover:bg-slate-50 transition-colors">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-slate-500 flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5 text-blue-600" />
              Daily Summary
            </span>
            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-blue-100 text-blue-800">DAILY</span>
          </div>
          <p className="text-sm font-bold text-slate-800">
            {data.latest_daily_summary_date ? formatDate(data.latest_daily_summary_date) : 'Not available yet'}
          </p>
          <p className="text-xs text-slate-500 mt-1">Aggregated Daily Records</p>
        </div>

        {/* 4. Pipeline Health & DQ */}
        <div className="p-4 rounded-xl border border-slate-100 bg-slate-50/40 hover:bg-slate-50 transition-colors">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-slate-500 flex items-center gap-1.5">
              <Activity className="w-3.5 h-3.5 text-purple-600" />
              Pipeline Health & DQ
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
          <p className="text-sm font-bold text-slate-800">
            {data.latest_pipeline_health_status === 'WARNING'
              ? 'Active with DQ Notices'
              : data.latest_pipeline_health_status || 'Checking...'}
          </p>
          <p className="text-xs text-slate-500 mt-1">SLA Freshness & Data Quality</p>
        </div>
      </div>

      {/* DAG Success Run Mini-Grid */}
      {data.latest_successful_dag_runs && data.latest_successful_dag_runs.length > 0 && (
        <div className="px-6 pb-5">
          <div className="border-t border-slate-100 pt-4">
            <h4 className="text-xs font-bold text-slate-600 mb-3 uppercase tracking-wider">Airflow Orchestration Runs</h4>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
              {data.latest_successful_dag_runs.map((dag) => (
                <div key={dag.dag_id} className="p-2 rounded-lg bg-slate-50 border border-slate-100 text-center">
                  <span
                    className={`inline-block w-2 h-2 rounded-full mb-1 ${
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
        </div>
      )}

      {/* Warnings if any */}
      {data.warnings && data.warnings.length > 0 && (
        <div className="px-6 pb-4">
          <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold mb-0.5">Freshness Notices:</p>
              <ul className="list-disc list-inside space-y-0.5 text-amber-700">
                {data.warnings.map((w, idx) => (
                  <li key={idx}>{w}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default FreshnessCard;
