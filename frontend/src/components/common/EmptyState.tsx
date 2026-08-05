import React from 'react';
import { Inbox } from 'lucide-react';

interface EmptyStateProps {
  title?: string;
  message?: string;
  height?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title = 'No Data Available',
  message = 'There are currently no records available to display for the selected parameters.',
  height = 'h-64',
}) => {
  return (
    <div className={`flex flex-col items-center justify-center ${height} bg-white rounded-xl border border-slate-200 p-6 text-center`}>
      <div className="p-3 bg-slate-100 rounded-full text-slate-400 mb-3">
        <Inbox className="w-6 h-6" />
      </div>
      <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
      <p className="text-xs text-slate-500 max-w-sm mt-1">{message}</p>
    </div>
  );
};

export default EmptyState;
