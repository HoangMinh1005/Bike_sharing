import React from 'react';
import { Calendar } from 'lucide-react';

interface DateFilterProps {
  label?: string;
  value?: string;
  onChange: (value: string) => void;
}

export const DateFilter: React.FC<DateFilterProps> = ({
  label = 'Summary Date',
  value = '',
  onChange,
}) => {
  return (
    <div className="flex items-center space-x-2">
      <label className="text-xs font-semibold text-slate-600 flex items-center gap-1.5">
        <Calendar className="w-3.5 h-3.5 text-slate-400" />
        {label}:
      </label>
      <input
        type="date"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="px-3 py-1.5 bg-white border border-slate-300 rounded-lg text-xs text-slate-800 font-medium focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 shadow-sm"
      />
    </div>
  );
};

export default DateFilter;
