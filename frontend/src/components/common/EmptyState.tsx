import React from 'react';
import { Inbox, Sparkles, RefreshCw } from 'lucide-react';

export interface EmptyStateProps {
  title?: string;
  message?: string;
  actionLabel?: string;
  onAction?: () => void;
  icon?: React.ReactNode;
  height?: string;
  severity?: 'info' | 'warning';
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title = 'No data available yet',
  message = 'The pipeline is running, but this dataset has not accumulated enough records yet.',
  actionLabel,
  onAction,
  icon,
  height = 'min-h-64',
  severity = 'info',
}) => {
  const isWarning = severity === 'warning';

  return (
    <div
      className={`flex flex-col items-center justify-center ${height} ${
        isWarning ? 'bg-amber-50/40 border-amber-200' : 'bg-slate-50/50 border-slate-200'
      } rounded-xl border p-6 text-center shadow-xs transition-all`}
    >
      <div
        className={`p-3.5 rounded-full mb-3 shadow-xs ${
          isWarning ? 'bg-amber-100 text-amber-600' : 'bg-white border border-slate-200 text-indigo-500'
        }`}
      >
        {icon ? icon : isWarning ? <Sparkles className="w-6 h-6" /> : <Inbox className="w-6 h-6" />}
      </div>

      <h3 className={`text-sm font-bold ${isWarning ? 'text-amber-900' : 'text-slate-800'}`}>{title}</h3>
      <p className={`text-xs ${isWarning ? 'text-amber-700' : 'text-slate-500'} max-w-sm mt-1 leading-relaxed`}>{message}</p>

      {onAction && actionLabel && (
        <button
          onClick={onAction}
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

export default EmptyState;
