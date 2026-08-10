import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import EmptyState from '../common/EmptyState';

export interface LineSeries {
  key: string;
  name: string;
  color: string;
  yAxisId?: string;
  valueFormatter?: (value: number) => string;
}

interface LineChartCardProps {
  title: string;
  subtitle?: string;
  data: Record<string, any>[];
  xAxisKey: string;
  series: LineSeries[];
  valueFormatter?: (value: number) => string;
  rightYAxis?: {
    yAxisId: string;
    valueFormatter?: (value: number) => string;
  };
  height?: number;
}

export const LineChartCard: React.FC<LineChartCardProps> = ({
  title,
  subtitle,
  data,
  xAxisKey,
  series,
  valueFormatter = (v) => String(v),
  rightYAxis,
  height = 280,
}) => {
  if (!data || data.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <h3 className="text-sm font-bold text-slate-800 mb-1">{title}</h3>
        {subtitle && <p className="text-xs text-slate-500 mb-3">{subtitle}</p>}
        <EmptyState title="No Trend Data" message="No data available for chart visualization." height="h-56" />
      </div>
    );
  }

  const hasRightAxis = rightYAxis || series.some((s) => s.yAxisId === 'right');

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
      <h3 className="text-sm font-bold text-slate-800">{title}</h3>
      {subtitle && <p className="text-xs text-slate-500 mb-4">{subtitle}</p>}

      <div style={{ width: '100%', height }}>
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 10, right: hasRightAxis ? 10 : 20, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis
              dataKey={xAxisKey}
              stroke="#94a3b8"
              fontSize={11}
              tickLine={false}
            />
            <YAxis
              yAxisId="left"
              stroke="#94a3b8"
              fontSize={11}
              tickLine={false}
              tickFormatter={valueFormatter}
            />
            {hasRightAxis && (
              <YAxis
                yAxisId={rightYAxis?.yAxisId || 'right'}
                orientation="right"
                stroke="#f59e0b"
                fontSize={11}
                tickLine={false}
                tickFormatter={rightYAxis?.valueFormatter || ((v) => `${v.toFixed(1)}°C`)}
              />
            )}
            <Tooltip
              contentStyle={{
                backgroundColor: '#ffffff',
                borderColor: '#e2e8f0',
                borderRadius: '8px',
                fontSize: '12px',
                boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
              }}
              formatter={(value: any, name: any) => {
                const s = series.find((item) => item.name === name || item.key === name);
                if (typeof value === 'number') {
                  if (s?.valueFormatter) {
                    return [s.valueFormatter(value), s.name];
                  }
                  if (s?.yAxisId === 'right') {
                    return [
                      rightYAxis?.valueFormatter ? rightYAxis.valueFormatter(value) : `${value.toFixed(1)} °C`,
                      s.name,
                    ];
                  }
                  return [valueFormatter(value), s?.name || name];
                }
                return [value, s?.name || name];
              }}
            />
            <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }} />
            {series.map((s) => (
              <Line
                key={s.key}
                yAxisId={s.yAxisId || 'left'}
                type="monotone"
                dataKey={s.key}
                name={s.name}
                stroke={s.color}
                strokeWidth={2}
                dot={{ r: 3, fill: s.color }}
                activeDot={{ r: 5 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default LineChartCard;
