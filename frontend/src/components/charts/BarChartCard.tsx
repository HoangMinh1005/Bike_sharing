import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import EmptyState from '../common/EmptyState';

interface BarSeries {
  key: string;
  name: string;
  color: string;
}

interface BarChartCardProps {
  title: string;
  subtitle?: string;
  data: Record<string, any>[];
  xAxisKey: string;
  series: BarSeries[];
  valueFormatter?: (value: number) => string;
  height?: number;
  layout?: 'horizontal' | 'vertical';
}

export const BarChartCard: React.FC<BarChartCardProps> = ({
  title,
  subtitle,
  data,
  xAxisKey,
  series,
  valueFormatter = (v) => String(v),
  height = 280,
  layout = 'horizontal',
}) => {
  if (!data || data.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <h3 className="text-sm font-bold text-slate-800 mb-1">{title}</h3>
        {subtitle && <p className="text-xs text-slate-500 mb-3">{subtitle}</p>}
        <EmptyState title="No Chart Data" message="No data available for chart visualization." height="h-56" />
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
      <h3 className="text-sm font-bold text-slate-800">{title}</h3>
      {subtitle && <p className="text-xs text-slate-500 mb-4">{subtitle}</p>}

      <div style={{ width: '100%', height }}>
        <ResponsiveContainer>
          <BarChart data={data} layout={layout} margin={{ top: 10, right: 20, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            {layout === 'horizontal' ? (
              <>
                <XAxis dataKey={xAxisKey} stroke="#94a3b8" fontSize={11} tickLine={false} />
                <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} tickFormatter={valueFormatter} />
              </>
            ) : (
              <>
                <XAxis type="number" stroke="#94a3b8" fontSize={11} tickLine={false} tickFormatter={valueFormatter} />
                <YAxis dataKey={xAxisKey} type="category" stroke="#94a3b8" fontSize={11} tickLine={false} width={100} />
              </>
            )}
            <Tooltip
              contentStyle={{
                backgroundColor: '#ffffff',
                borderColor: '#e2e8f0',
                borderRadius: '8px',
                fontSize: '12px',
                boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
              }}
              formatter={(value: any) => [typeof value === 'number' ? valueFormatter(value) : value, '']}
            />
            <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }} />
            {series.map((s) => (
              <Bar key={s.key} dataKey={s.key} name={s.name} fill={s.color} radius={[4, 4, 0, 0]} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default BarChartCard;
