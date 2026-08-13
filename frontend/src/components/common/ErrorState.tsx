import React, { useState } from 'react';
import { AlertTriangle, Info, RefreshCw, ChevronDown, ChevronUp, ServerCrash } from 'lucide-react';

export interface ErrorStateProps {
  title?: string;
  message?: string;
  actionLabel?: string;
  onRetry?: () => void;
  severity?: 'info' | 'warning' | 'error';
  technicalDetails?: string | object;
  height?: string;
  icon?: React.ReactNode;
}

const severityConfig = {
  error: {
    bg: 'bg-rose-50/70',
    border: 'border-rose-200',
    iconBg: 'bg-rose-100',
    iconColor: 'text-rose-600',
    titleColor: 'text-rose-900',
    messageColor: 'text-rose-700',
    btnBg: 'bg-rose-600 hover:bg-rose-700 text-white',
    DefaultIcon: ServerCrash,
  },
  warning: {
    bg: 'bg-amber-50/70',
    border: 'border-amber-200',
    iconBg: 'bg-amber-100',
    iconColor: 'text-amber-600',
    titleColor: 'text-amber-900',
    messageColor: 'text-amber-700',
    btnBg: 'bg-amber-600 hover:bg-amber-700 text-white',
    DefaultIcon: AlertTriangle,
  },
  info: {
    bg: 'bg-slate-50',
    border: 'border-slate-200',
    iconBg: 'bg-indigo-50',
    iconColor: 'text-indigo-600',
    titleColor: 'text-slate-800',
    messageColor: 'text-slate-600',
    btnBg: 'bg-slate-800 hover:bg-slate-900 text-white',
    DefaultIcon: Info,
  },
};

export const ErrorState: React.FC<ErrorStateProps> = ({
  title,
  message = 'An unexpected error occurred while communicating with the server.',
  actionLabel = 'Retry',
  onRetry,
  severity = 'error',
  technicalDetails,
  height = 'min-h-64',
  icon,
}) => {
  const [showDetails, setShowDetails] = useState(false);
  const conf = severityConfig[severity] || severityConfig.error;
  const DefaultIcon = conf.DefaultIcon;

  const defaultTitle =
    severity === 'error'
      ? 'Backend service error'
      : severity === 'warning'
      ? 'Data not fully available'
      : 'No data recorded yet';

  const displayTitle = title || defaultTitle;
  const detailsStr =
    technicalDetails && typeof technicalDetails === 'object'
      ? JSON.stringify(technicalDetails, null, 2)
      : technicalDetails
      ? String(technicalDetails)
      : null;

  return (
    <div className={`flex flex-col items-center justify-center ${height} ${conf.bg} rounded-xl border ${conf.border} p-6 text-center shadow-xs transition-all`}>
      <div className={`p-3 ${conf.iconBg} rounded-full ${conf.iconColor} mb-3 shadow-xs`}>
        {icon ? icon : <DefaultIcon className="w-6 h-6" />}
      </div>
      <h3 className={`text-base font-bold ${conf.titleColor}`}>{displayTitle}</h3>
      <p className={`text-xs ${conf.messageColor} max-w-md mt-1.5 leading-relaxed`}>{message}</p>

      {/* Action Button */}
      {onRetry && (
        <button
          onClick={onRetry}
          className={`mt-4 inline-flex items-center px-4 py-2 rounded-lg text-xs font-semibold ${conf.btnBg} transition-all shadow-xs`}
        >
          <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
          {actionLabel}
        </button>
      )}

      {/* Technical Details Toggle */}
      {detailsStr && (
        <div className="mt-4 w-full max-w-md">
          <button
            onClick={() => setShowDetails(!showDetails)}
            className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-500 hover:text-slate-700 transition-colors"
          >
            {showDetails ? (
              <>
                <ChevronUp className="w-3 h-3" /> Hide technical details
              </>
            ) : (
              <>
                <ChevronDown className="w-3 h-3" /> Show technical details
              </>
            )}
          </button>
          {showDetails && (
            <div className="mt-2 text-left bg-slate-900 text-slate-200 p-3 rounded-lg text-[11px] font-mono overflow-x-auto border border-slate-700 shadow-inner">
              <pre>{detailsStr}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ErrorState;
