import React from 'react';
import { Loader2 } from 'lucide-react';

export interface LoadingStateProps {
  title?: string;
  message?: string;
  height?: string;
}

export const LoadingState: React.FC<LoadingStateProps> = ({
  title,
  message = 'Fetching live data from backend...',
  height = 'min-h-64',
}) => {
  return (
    <div className={`flex flex-col items-center justify-center ${height} bg-white rounded-xl border border-slate-200 p-6 text-center shadow-xs`}>
      <Loader2 className="w-7 h-7 text-indigo-600 animate-spin mb-3" />
      {title && <h4 className="text-sm font-bold text-slate-800 mb-1">{title}</h4>}
      <p className="text-xs text-slate-500 max-w-sm leading-relaxed">{message}</p>
    </div>
  );
};

export default LoadingState;
