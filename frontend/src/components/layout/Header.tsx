import React from 'react';
import { RefreshCw, CheckCircle, AlertCircle } from 'lucide-react';
import { useApiHealth } from '../../hooks/useHealth';
import { useQueryClient } from '@tanstack/react-query';

export const Header: React.FC = () => {
  const { data: healthData, isLoading, isError } = useApiHealth();
  const queryClient = useQueryClient();

  const handleRefresh = () => {
    queryClient.invalidateQueries();
  };

  const statusStr = healthData?.data?.status?.toLowerCase();
  const isHealthy = statusStr === 'ok' || statusStr === 'healthy';

  return (
    <header className="h-16 bg-white border-b border-slate-200 px-8 flex items-center justify-between sticky top-0 z-10 shadow-xs">
      {/* Title */}
      <div className="flex items-center gap-3">
        <h2 className="text-base font-bold text-slate-800 tracking-tight">GBFS Operations Intelligence</h2>
        <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-100 text-slate-600 border border-slate-200">
          FastAPI Serving
        </span>
      </div>

      {/* Actions & Health Badge */}
      <div className="flex items-center gap-4">
        {/* Health Status Indicator */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-semibold bg-slate-50 border-slate-200">
          {isLoading ? (
            <span className="text-slate-400">Checking API...</span>
          ) : isError ? (
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
