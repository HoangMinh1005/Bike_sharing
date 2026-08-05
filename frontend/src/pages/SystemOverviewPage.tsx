import React, { useState } from 'react';
import PageContainer from '../components/layout/PageContainer';
import KpiCard from '../components/common/KpiCard';
import SectionTitle from '../components/common/SectionTitle';
import LoadingState from '../components/common/LoadingState';
import ErrorState from '../components/common/ErrorState';
import LineChartCard from '../components/charts/LineChartCard';
import BarChartCard from '../components/charts/BarChartCard';
import DataTable, { Column } from '../components/table/DataTable';
import DateFilter from '../components/common/DateFilter';
import { useSystemDaily, useSystemHourly, useSystemLatest } from '../hooks/useSystem';
import { formatDate, formatNumber, formatPercent } from '../utils/format';
import { getPastDateString } from '../utils/date';
import { SystemDailySummary } from '../types/system';
import { Bike, Layers, MapPin, Activity, Thermometer, Sun } from 'lucide-react';

export const SystemOverviewPage: React.FC = () => {
  const [selectedDate, setSelectedDate] = useState<string>('');

  const { data: latestRes, isLoading: isLatestLoading, isError: isLatestError, refetch: refetchLatest } = useSystemLatest();

  const latestDate = latestRes?.data?.summary_date;
  const effectiveDate = selectedDate || latestDate || '';

  const { data: dailyRes } = useSystemDaily(
    effectiveDate ? { start_date: getPastDateString(14, effectiveDate), end_date: effectiveDate } : undefined
  );
  const { data: hourlyRes } = useSystemHourly({ limit: 24 });

  if (isLatestLoading) {
    return (
      <PageContainer title="System Overview">
        <LoadingState message="Fetching system latest summary..." />
      </PageContainer>
    );
  }

  if (isLatestError || !latestRes?.data) {
    return (
      <PageContainer title="System Overview">
        <ErrorState message="Could not load system metrics from FastAPI backend." onRetry={refetchLatest} />
      </PageContainer>
    );
  }

  const dailyList = dailyRes?.data || [latestRes.data];
  const activeSummary = dailyList.find((item) => item.summary_date === effectiveDate) || dailyList[dailyList.length - 1] || latestRes.data;
  const hourlyList = hourlyRes?.data || [];

  // Chart data formatting
  const dailyChartData = dailyList.map((item) => ({
    date: formatDate(item.summary_date),
    availabilityRate: item.avg_availability_rate ? item.avg_availability_rate * 100 : 0,
    utilizationRate: item.avg_dock_utilization_rate ? item.avg_dock_utilization_rate * 100 : 0,
    bikesAvailable: item.total_bikes_available || item.avg_bikes_available || 0,
    docksAvailable: item.total_docks_available || item.avg_docks_available || 0,
  }));

  const hourlyChartData = hourlyList.map((item) => ({
    hour: item.hour_bucket ? item.hour_bucket.substring(11, 16) : '-',
    availabilityRate: item.avg_availability_rate ? item.avg_availability_rate * 100 : 0,
    utilizationRate: item.avg_dock_utilization_rate ? item.avg_dock_utilization_rate * 100 : 0,
    temperature: item.temperature || 0,
  }));

  const dailyTableColumns: Column<SystemDailySummary>[] = [
    { key: 'summary_date', header: 'Summary Date', render: (r) => formatDate(r.summary_date) },
    { key: 'active_station_count', header: 'Active Stations', align: 'right', render: (r) => formatNumber(r.active_station_count) },
    { key: 'avg_availability_rate', header: 'Availability Rate', align: 'right', render: (r) => formatPercent(r.avg_availability_rate) },
    { key: 'avg_dock_utilization_rate', header: 'Dock Utilization', align: 'right', render: (r) => formatPercent(r.avg_dock_utilization_rate) },
    { key: 'total_bikes_available', header: 'Bikes Available', align: 'right', render: (r) => formatNumber(r.total_bikes_available || r.avg_bikes_available) },
    { key: 'total_docks_available', header: 'Docks Available', align: 'right', render: (r) => formatNumber(r.total_docks_available || r.avg_docks_available) },
    { key: 'avg_temperature', header: 'Avg Temp (°C)', align: 'right', render: (r) => (r.avg_temperature !== undefined ? `${r.avg_temperature.toFixed(1)}°C` : '-') },
  ];

  return (
    <PageContainer
      title="System Overview"
      description={`System-wide operational metrics for ${formatDate(activeSummary.summary_date)}`}
      action={<DateFilter value={effectiveDate} onChange={setSelectedDate} />}
    >
      {/* Top KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
        <KpiCard
          title="Summary Date"
          value={formatDate(activeSummary.summary_date)}
          subtitle={activeSummary.is_weekend ? 'Weekend' : activeSummary.is_holiday ? `Holiday: ${activeSummary.holiday_name}` : 'Weekday'}
          icon={Sun}
        />
        <KpiCard
          title="Active Stations"
          value={formatNumber(activeSummary.active_station_count)}
          subtitle={`Out of ${formatNumber(activeSummary.station_count)} total stations`}
          icon={MapPin}
        />
        <KpiCard
          title="Avg Availability Rate"
          value={formatPercent(activeSummary.avg_availability_rate)}
          subtitle="System-wide bike availability"
          icon={Bike}
        />
        <KpiCard
          title="Avg Dock Utilization"
          value={formatPercent(activeSummary.avg_dock_utilization_rate)}
          subtitle="System-wide dock usage"
          icon={Layers}
        />
      </div>

      {/* Additional Operational KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-5 mb-8">
        <KpiCard
          title="Bikes / Docks Capacity"
          value={`${formatNumber(activeSummary.total_bikes_available || activeSummary.avg_bikes_available)} / ${formatNumber(activeSummary.total_docks_available || activeSummary.avg_docks_available)}`}
          subtitle="Available bikes vs docks"
          icon={Activity}
        />
        <KpiCard
          title="High Demand Stations"
          value={formatNumber(activeSummary.high_demand_station_count)}
          subtitle={`${formatNumber(activeSummary.empty_station_count)} empty stations`}
          status={activeSummary.high_demand_station_count && activeSummary.high_demand_station_count > 50 ? 'WARNING' : 'HEALTHY'}
        />
        <KpiCard
          title="Avg Temperature"
          value={activeSummary.avg_temperature !== undefined ? `${activeSummary.avg_temperature.toFixed(1)} °C` : '-'}
          subtitle={activeSummary.total_precipitation ? `Precipitation: ${activeSummary.total_precipitation} mm` : 'Dry conditions'}
          icon={Thermometer}
        />
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <LineChartCard
          title="Availability & Dock Utilization Trend (%)"
          subtitle="Daily system-wide percentage rates"
          data={dailyChartData}
          xAxisKey="date"
          series={[
            { key: 'availabilityRate', name: 'Availability Rate (%)', color: '#16a34a' },
            { key: 'utilizationRate', name: 'Dock Utilization (%)', color: '#0284c7' },
          ]}
          valueFormatter={(v) => `${v.toFixed(1)}%`}
        />

        <BarChartCard
          title="Total Bikes vs Docks Available"
          subtitle="System inventory comparison"
          data={dailyChartData}
          xAxisKey="date"
          series={[
            { key: 'bikesAvailable', name: 'Bikes Available', color: '#22c55e' },
            { key: 'docksAvailable', name: 'Docks Available', color: '#94a3b8' },
          ]}
          valueFormatter={(v) => formatNumber(v)}
        />
      </div>

      {/* Hourly System Mobility Chart */}
      {hourlyList.length > 0 && (
        <div className="mb-8">
          <LineChartCard
            title="Recent Hourly Mobility Rate (%)"
            subtitle="Hourly system availability and weather temperature"
            data={hourlyChartData}
            xAxisKey="hour"
            series={[
              { key: 'availabilityRate', name: 'Hourly Availability (%)', color: '#10b981' },
              { key: 'utilizationRate', name: 'Hourly Utilization (%)', color: '#6366f1' },
            ]}
            valueFormatter={(v) => `${v.toFixed(1)}%`}
          />
        </div>
      )}

      {/* Daily Summaries Data Table */}
      <div>
        <SectionTitle title="Daily System Summaries" subtitle="Historical daily system aggregation records" />
        <DataTable
          columns={dailyTableColumns}
          data={dailyList}
          keyExtractor={(row) => row.summary_date}
        />
      </div>
    </PageContainer>
  );
};

export default SystemOverviewPage;
