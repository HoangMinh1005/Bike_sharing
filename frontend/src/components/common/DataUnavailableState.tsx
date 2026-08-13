import React from 'react';
import { Database, RefreshCw, Calendar, Layers } from 'lucide-react';

export interface DataUnavailableStateProps {
  title?: string;
  message?: string;
  reason?: string;
  onRetry?: () => void;
  actionLabel?: string;
  severity?: 'info' | 'warning';
  height?: string;
  iconType?: 'database' | 'calendar' | 'layers';
}

export const DataUnavailableState: React.FC<DataUnavailableStateProps> = ({
  title = 'Data is not ready yet',
  message = 'This aggregation requires hourly observations to be recorded first.',
  reason,
  onRetry,
  actionLabel = 'Check again',
  severity = 'info',
  height = 'min-h-64',
  iconType = 'database',
}) => {
  const isWarning = severity === 'warning';

  const getIcon = () => {
    switch (iconType) {
      case 'calendar':
        return <Calendar className="w-6 h-6" />;
      case 'layers':
        return <Layers className="w-6 h-6" />;
      default:
        return <Database className="w-6 h-6" />;
    }
  };

  return (
    <div
      className={`flex flex-col items-center justify-center ${height} ${
        isWarning ? 'bg-amber-50/50 border-amber-200' : 'bg-slate-50 border-slate-200'
      } rounded-xl border p-6 text-center shadow-xs transition-all`}
    >
      <div
        className={`p-3.5 rounded-full mb-3 shadow-xs ${
          isWarning ? 'bg-amber-100 text-amber-600' : 'bg-indigo-50 text-indigo-600 border border-indigo-100'
        }`}
      >
        {getIcon()}
      </div>

      <h3 className={`text-sm font-bold ${isWarning ? 'text-amber-900' : 'text-slate-800'}`}>{title}</h3>
      <p className={`text-xs ${isWarning ? 'text-amber-700' : 'text-slate-600'} max-w-md mt-1.5 leading-relaxed`}>{message}</p>

      {reason && (
        <div className="mt-3 px-3 py-1.5 rounded-lg bg-white/80 border border-slate-200 text-[11px] text-slate-500 max-w-sm">
          <span className="font-semibold text-slate-700">Requirement:</span> {reason}
        </div>
      )}

      {onRetry && (
        <button
          onClick={onRetry}
          className={`mt-4 inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold ${
            isWarning
              ? 'bg-amber-600 hover:bg-amber-700 text-white'
              : 'bg-slate-800 hover:bg-slate-900 text-white'
          } transition-colors shadow-xs`}
        >
          <RefreshCw className="w-3.5 h-3.5" />
          {actionLabel}
        </button>
      )}
    </div>
  );
};

export default DataUnavailableState;
