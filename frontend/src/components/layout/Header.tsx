import React from 'react';
import { RefreshCw, CheckCircle, AlertCircle, AlertTriangle, Clock } from 'lucide-react';
import { useApiHealth } from '../../hooks/useHealth';
import { useFreshnessSummary } from '../../hooks/useFreshness';
import { useQueryClient } from '@tanstack/react-query';

export const Header: React.FC = () => {
  const { data: healthData, isLoading: isHealthLoading, isError: isHealthError } = useApiHealth();
  const { data: freshnessRes, isLoading: isFreshnessLoading } = useFreshnessSummary();
  const queryClient = useQueryClient();

  const handleRefresh = () => {
    queryClient.invalidateQueries();
  };

  const statusStr = healthData?.data?.status?.toLowerCase();
  const isHealthy = statusStr === 'ok' || statusStr === 'healthy';

  const freshnessData = freshnessRes?.data;
  const freshnessStatus = freshnessData?.status || 'UNKNOWN';

  const getFreshnessBadge = () => {
    if (isFreshnessLoading) {
      return (
        <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold bg-slate-50 text-slate-400 border border-slate-200">
          <Clock className="w-3.5 h-3.5 animate-spin" />
          Freshness...
        </span>
      );
    }
    if (freshnessStatus === 'HEALTHY') {
      return (
        <span
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200"
          title={`Data is Live. Station Lag: ${freshnessData?.station_status_lag_minutes ?? '-'} min`}
        >
          <CheckCircle className="w-3.5 h-3.5 text-emerald-500" />
          Data: Live
        </span>
      );
    }
    if (freshnessStatus === 'WARNING') {
      return (
        <span
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold bg-amber-50 text-amber-700 border border-amber-200"
          title={`Data is Lagging. Mart Lag: ${freshnessData?.hourly_mart_lag_minutes ?? '-'} min`}
        >
          <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
          Data: Lagging
        </span>
      );
    }
    if (freshnessStatus === 'STALE') {
      return (
        <span
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold bg-rose-50 text-rose-700 border border-rose-200"
          title="Data is Stale (>1h snapshot or >4h mart lag)"
        >
          <AlertCircle className="w-3.5 h-3.5 text-rose-500" />
          Data: Stale
        </span>
      );
    }
    return (
      <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-50 text-slate-600 border border-slate-200">
        <Clock className="w-3.5 h-3.5 text-slate-400" />
        Data: Pending
      </span>
    );
  };

  return (
    <header className="h-16 bg-white border-b border-slate-200 px-8 flex items-center justify-between sticky top-0 z-10 shadow-xs">
      {/* Title */}
      <div className="flex items-center gap-3">
        <h2 className="text-base font-bold text-slate-800 tracking-tight">GBFS Operations Intelligence</h2>
        <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-100 text-slate-600 border border-slate-200">
          FastAPI Serving
        </span>
      </div>

      {/* Actions & Badges */}
      <div className="flex items-center gap-3">
        {/* Data Freshness Indicator */}
        {getFreshnessBadge()}

        {/* API Health Status Indicator */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-semibold bg-slate-50 border-slate-200">
          {isHealthLoading ? (
            <span className="text-slate-400">Checking API...</span>
          ) : isHealthError ? (
            <>
              <AlertCircle className="w-3.5 h-3.5 text-rose-500" />
              <span className="text-rose-600">API Offline</span>
            </>
          ) : isHealthy ? (
            <>
              <CheckCircle className="w-3.5 h-3.5 text-emerald-500" />
              <span className="text-emerald-700">API Online</span>
            </>
          ) : (
            <>
              <AlertCircle className="w-3.5 h-3.5 text-amber-500" />
              <span className="text-amber-700">API Degraded</span>
            </>
          )}
        </div>

        {/* Refresh Button */}
        <button
          onClick={handleRefresh}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 text-slate-700 hover:bg-slate-200 transition-colors border border-slate-200"
          title="Refresh All Dashboard Data"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </button>
      </div>
    </header>
  );
};

export default Header;
