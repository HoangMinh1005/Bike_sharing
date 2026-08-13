import React from 'react';
import { AlertTriangle, Info } from 'lucide-react';

export interface PartialDataWarningProps {
  title?: string;
  message?: string;
  missingSources?: string[];
  severity?: 'warning' | 'info';
  className?: string;
}

export const PartialDataWarning: React.FC<PartialDataWarningProps> = ({
  title = 'Partial data available',
  message = 'Some metrics are available, but a few data sources are still missing or not fresh.',
  missingSources,
  severity = 'warning',
  className = '',
}) => {
  const isWarning = severity === 'warning';

  return (
    <div
      className={`rounded-xl border p-4 mb-6 shadow-xs flex items-start gap-3.5 ${
        isWarning ? 'bg-amber-50/80 border-amber-200 text-amber-900' : 'bg-blue-50/80 border-blue-200 text-blue-900'
      } ${className}`}
    >
      <div className={`p-1.5 rounded-lg shrink-0 mt-0.5 ${isWarning ? 'bg-amber-100 text-amber-700' : 'bg-blue-100 text-blue-700'}`}>
        {isWarning ? <AlertTriangle className="w-4 h-4" /> : <Info className="w-4 h-4" />}
      </div>

      <div className="flex-1 text-xs">
        <h4 className="font-bold text-sm mb-0.5">{title}</h4>
        <p className={`${isWarning ? 'text-amber-800' : 'text-blue-800'} leading-relaxed`}>{message}</p>

        {missingSources && missingSources.length > 0 && (
          <div className="mt-2 pt-2 border-t border-amber-200/60">
            <span className="font-semibold text-[11px] uppercase tracking-wider text-amber-700">Pending Components:</span>
            <ul className="list-disc list-inside mt-1 space-y-0.5 text-amber-800 text-[11px]">
              {missingSources.map((source, idx) => (
                <li key={idx}>{source}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
};

export default PartialDataWarning;
