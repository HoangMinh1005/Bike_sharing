import React from 'react';
import { Loader2 } from 'lucide-react';

interface LoadingStateProps {
  message?: string;
  height?: string;
}

export const LoadingState: React.FC<LoadingStateProps> = ({
  message = 'Loading data...',
  height = 'h-64',
}) => {
  return (
    <div className={`flex flex-col items-center justify-center ${height} bg-white rounded-xl border border-slate-200 p-6`}>
      <Loader2 className="w-8 h-8 text-emerald-600 animate-spin mb-3" />
      <p className="text-sm font-medium text-slate-600">{message}</p>
    </div>
  );
};

export default LoadingState;
