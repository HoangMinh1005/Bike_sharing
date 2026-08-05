import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = 'Failed to load data',
  message = 'An unexpected error occurred while communicating with the server.',
  onRetry,
}) => {
  return (
    <div className="flex flex-col items-center justify-center h-64 bg-rose-50/50 rounded-xl border border-rose-200 p-6 text-center">
      <div className="p-3 bg-rose-100 rounded-full text-rose-600 mb-3">
        <AlertTriangle className="w-6 h-6" />
      </div>
      <h3 className="text-base font-semibold text-rose-900">{title}</h3>
      <p className="text-xs text-rose-700 max-w-md mt-1 mb-4">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="inline-flex items-center px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-rose-600 text-white hover:bg-rose-700 transition-colors shadow-sm"
        >
          <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
          Retry
        </button>
      )}
    </div>
  );
};

export default ErrorState;
