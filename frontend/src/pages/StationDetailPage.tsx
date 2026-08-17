import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import PageContainer from '../components/layout/PageContainer';
import KpiCard from '../components/common/KpiCard';
import SectionTitle from '../components/common/SectionTitle';
import LoadingState from '../components/common/LoadingState';
import ErrorState from '../components/common/ErrorState';
import EmptyState from '../components/common/EmptyState';
import LineChartCard from '../components/charts/LineChartCard';
import DataTable, { Column } from '../components/table/DataTable';
import { getPastDateString, getTodayDateString } from '../utils/date';
import { useStationDaily, useStationHourly } from '../hooks/useStations';
import { formatDate, formatNumber, formatPercent } from '../utils/format';
import { parseApiError } from '../utils/error';
import { StationDailySummary } from '../types/station';
import { ArrowLeft, MapPin, Bike, Layers, Clock } from 'lucide-react';

export const StationDetailPage: React.FC = () => {
  const { stationId } = useParams<{ stationId: string }>();
  const navigate = useNavigate();

  const todayStr = getTodayDateString();
  const past30Str = getPastDateString(30);

  const {
    data: dailyRes,
    isLoading: isDailyLoading,
    isError: isDailyError,
    error: dailyError,
    refetch: refetchDaily,
  } = useStationDaily(stationId || '', { start_date: past30Str, end_date: todayStr });

  const { data: hourlyRes, isLoading: isHourlyLoading } = useStationHourly(
    stationId || '',
    { start_time: `${todayStr}T00:00:00`, end_time: `${todayStr}T23:59:59`, limit: 24 }
  );

  if (!stationId) {
    return (
      <PageContainer title="Station Detail">
        <ErrorState
          title="Invalid Station ID"
          message="No valid station identifier provided in the URL route path."
          severity="warning"
          actionLabel="Back to Stations"
          onRetry={() => navigate('/stations')}
        />
      </PageContainer>
    );
  }

  if (isDailyLoading && isHourlyLoading) {
    return (
      <PageContainer title={`Station: ${stationId}`}>
        <LoadingState title={`Fetching Station ${stationId}`} message="Retrieving station metrics and daily summary..." />
      </PageContainer>
    );
  }

  const parsedError = isDailyError ? parseApiError(dailyError, `No historical daily data found for station '${stationId}'.`) : null;

  if (parsedError && (parsedError.isNetworkError || parsedError.isServerError)) {
    return (
      <PageContainer title={`Station: ${stationId}`}>
        <ErrorState
          title={parsedError.title}
          message={parsedError.message}
          severity={parsedError.severity}
          technicalDetails={parsedError.technicalDetails}
          actionLabel="Retry"
          onRetry={refetchDaily}
        />
      </PageContainer>
    );
  }

  if (!dailyRes?.data || dailyRes.data.length === 0) {
    return (
      <PageContainer title={`Station: ${stationId}`}>
        <div className="mb-4">
          <button
            onClick={() => navigate('/stations')}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-slate-900 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Back to Stations
          </button>
        </div>
        <EmptyState
          title={`No history for station '${stationId}' yet`}
          message="Real-time observations are being collected, but daily aggregations have not been computed yet for this station."
          actionLabel="Refresh Data"
          onAction={refetchDaily}
        />
      </PageContainer>
    );
  }

  const dailyHistory = dailyRes.data;
  const sortedHistoryAsc = [...dailyHistory].sort(
    (a, b) => new Date(a.summary_date).getTime() - new Date(b.summary_date).getTime()
  );
  const latestSummary = sortedHistoryAsc[sortedHistoryAsc.length - 1];
  const hourlyData = hourlyRes?.data || [];

  // Chart data formatting
  const hourlyChartData = hourlyData.map((h) => ({
    hour: h.hour_bucket ? h.hour_bucket.substring(11, 16) : '-',
    availabilityRate: h.availability_rate ? h.availability_rate * 100 : 0,
    dockUtilization: h.dock_utilization_rate ? h.dock_utilization_rate * 100 : 0,
    bikesAvailable: h.avg_bikes_available || 0,
    docksAvailable: h.avg_docks_available || 0,
  }));

  const dailyTrendData = sortedHistoryAsc.map((d) => ({
    date: formatDate(d.summary_date),
    availabilityRate: d.avg_availability_rate ? d.avg_availability_rate * 100 : 0,
    dockUtilization: d.avg_dock_utilization_rate ? d.avg_dock_utilization_rate * 100 : 0,
  }));
  const tableDataDesc = [...sortedHistoryAsc].reverse();

  const dailyColumns: Column<StationDailySummary>[] = [
    { key: 'summary_date', header: 'Date', render: (r) => formatDate(r.summary_date) },
    { key: 'avg_availability_rate', header: 'Availability Rate', align: 'right', render: (r) => formatPercent(r.avg_availability_rate) },
    { key: 'avg_dock_utilization_rate', header: 'Dock Utilization', align: 'right', render: (r) => formatPercent(r.avg_dock_utilization_rate) },
    { key: 'avg_bikes_available', header: 'Avg Bikes Available', align: 'right', render: (r) => formatNumber(r.avg_bikes_available, 1) },
    { key: 'avg_docks_available', header: 'Avg Docks Available', align: 'right', render: (r) => formatNumber(r.avg_docks_available, 1) },
    { key: 'active_hour_count', header: 'Active Hours', align: 'right', render: (r) => formatNumber(r.active_hour_count) },
    { key: 'empty_hour_count', header: 'Empty Hours', align: 'right', render: (r) => formatNumber(r.empty_hour_count) },
  ];

  return (
    <PageContainer
      title={latestSummary.station_name || stationId}
      description={`Station ID: ${stationId} • Region: ${latestSummary.region_name || latestSummary.region_id || 'N/A'}`}
      action={
        <button
          onClick={() => navigate('/stations')}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 text-slate-700 hover:bg-slate-200 transition-colors border border-slate-200"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back to Stations
        </button>
      }
    >
      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
        <KpiCard
          title="Station Capacity"
          value={formatNumber(latestSummary.capacity)}
          subtitle="Total dock capacity"
          icon={MapPin}
        />
        <KpiCard
          title="Avg Availability Rate"
          value={formatPercent(latestSummary.avg_availability_rate)}
          subtitle="Station bike availability"
          icon={Bike}
        />
        <KpiCard
          title="Avg Dock Utilization"
          value={formatPercent(latestSummary.avg_dock_utilization_rate)}
          subtitle="Station dock occupancy"
          icon={Layers}
        />
        <KpiCard
          title="Active Hours"
          value={formatNumber(latestSummary.active_hour_count)}
          subtitle={`Out of 24 operating hours`}
          icon={Clock}
        />
      </div>

      {/* Hourly Availability Chart */}
      {hourlyChartData.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          <LineChartCard
            title="Hourly Availability & Dock Utilization Rate (%)"
            subtitle="24-hour observation buckets"
            data={hourlyChartData}
            xAxisKey="hour"
            series={[
              { key: 'availabilityRate', name: 'Availability Rate (%)', color: '#16a34a' },
              { key: 'dockUtilization', name: 'Dock Utilization (%)', color: '#0284c7' },
            ]}
            valueFormatter={(v) => `${v.toFixed(1)}%`}
          />

          <LineChartCard
            title="Hourly Available Bikes vs Docks"
            subtitle="Inventory availability across day"
            data={hourlyChartData}
            xAxisKey="hour"
            series={[
              { key: 'bikesAvailable', name: 'Bikes Available', color: '#22c55e' },
              { key: 'docksAvailable', name: 'Docks Available', color: '#94a3b8' },
            ]}
            valueFormatter={(v) => formatNumber(v, 1)}
          />
        </div>
      )}

      {/* Daily Availability Trend */}
      {dailyTrendData.length > 1 && (
        <div className="mb-8">
          <LineChartCard
            title="Daily Availability Trend (%)"
            subtitle="Historical availability rates over summary dates"
            data={dailyTrendData}
            xAxisKey="date"
            series={[
              { key: 'availabilityRate', name: 'Availability Rate (%)', color: '#10b981' },
              { key: 'dockUtilization', name: 'Dock Utilization (%)', color: '#6366f1' },
            ]}
            valueFormatter={(v) => `${v.toFixed(1)}%`}
          />
        </div>
      )}

      {/* Daily History Table */}
      <div>
        <SectionTitle title="Daily Performance History" subtitle="Historical daily records for station" />
        <DataTable
          columns={dailyColumns}
          data={tableDataDesc}
          keyExtractor={(row) => row.summary_date}
        />
      </div>
    </PageContainer>
  );
};

export default StationDetailPage;
