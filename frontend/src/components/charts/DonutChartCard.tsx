import React from 'react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import EmptyState from '../common/EmptyState';

interface DonutDataItem {
  name: string;
  value: number;
  color: string;
}

interface DonutChartCardProps {
  title: string;
  subtitle?: string;
  data: DonutDataItem[];
  height?: number;
}

export const DonutChartCard: React.FC<DonutChartCardProps> = ({
  title,
  subtitle,
  data,
  height = 280,
}) => {
  if (!data || data.length === 0 || data.every((d) => d.value === 0)) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <h3 className="text-sm font-bold text-slate-800 mb-1">{title}</h3>
        {subtitle && <p className="text-xs text-slate-500 mb-3">{subtitle}</p>}
        <EmptyState title="No Category Data" message="No data available for category chart." height="h-56" />
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
      <h3 className="text-sm font-bold text-slate-800">{title}</h3>
      {subtitle && <p className="text-xs text-slate-500 mb-4">{subtitle}</p>}

      <div style={{ width: '100%', height }}>
        <ResponsiveContainer>
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={55}
              outerRadius={85}
              paddingAngle={4}
              dataKey="value"
            >
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                backgroundColor: '#ffffff',
                borderColor: '#e2e8f0',
                borderRadius: '8px',
                fontSize: '12px',
                boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
              }}
            />
            <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }} />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default DonutChartCard;
