import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import PageContainer from '../components/layout/PageContainer';
import KpiCard from '../components/common/KpiCard';
import SectionTitle from '../components/common/SectionTitle';
import LoadingState from '../components/common/LoadingState';
import ErrorState from '../components/common/ErrorState';
import LineChartCard from '../components/charts/LineChartCard';
import DataTable, { Column } from '../components/table/DataTable';
import DateFilter from '../components/common/DateFilter';
import { useRegionDaily, useRegionStations } from '../hooks/useRegions';
import { useSystemLatest } from '../hooks/useSystem';
import { formatDate, formatNumber, formatPercent } from '../utils/format';
import { StationDailySummary } from '../types/station';
import { ArrowLeft, Compass, MapPin, Bike, Layers } from 'lucide-react';

export const RegionDetailPage: React.FC = () => {
  const { regionId } = useParams<{ regionId: string }>();
  const navigate = useNavigate();
  const [summaryDate, setSummaryDate] = useState<string>('');

  const { data: latestRes } = useSystemLatest();
  const latestDate = latestRes?.data?.summary_date;
  const effectiveDate = summaryDate || latestDate || '';

  const { data: dailyRes, isLoading: isDailyLoading, isError: isDailyError, refetch: refetchDaily } = useRegionDaily(regionId || '');
  const { data: stationsRes, isLoading: isStationsLoading } = useRegionStations(regionId || '', { summary_date: effectiveDate });

  if (!regionId) {
    return (
      <PageContainer title="Region Detail">
        <ErrorState message="No region ID provided in route path." />
      </PageContainer>
    );
  }

  if (isDailyLoading || isStationsLoading) {
    return (
      <PageContainer title={`Region: ${regionId}`}>
        <LoadingState message={`Fetching region detail for ${regionId}...`} />
      </PageContainer>
    );
  }

  if (isDailyError || !dailyRes?.data || dailyRes.data.length === 0) {
    return (
      <PageContainer title={`Region: ${regionId}`}>
        <ErrorState message={`No daily history found for region ID '${regionId}'.`} onRetry={refetchDaily} />
      </PageContainer>
    );
  }

  const dailyHistory = dailyRes.data;
  const latestSummary = dailyHistory[0];
  const regionStations = stationsRes?.data || [];

  const dailyTrendData = [...dailyHistory].reverse().map((d) => ({
    date: formatDate(d.summary_date),
    availabilityRate: d.avg_availability_rate ? d.avg_availability_rate * 100 : 0,
    dockUtilization: d.avg_dock_utilization_rate ? d.avg_dock_utilization_rate * 100 : 0,
  }));

  const stationColumns: Column<StationDailySummary>[] = [
    { key: 'station_id', header: 'Station ID', render: (r) => <span className="font-mono font-medium text-slate-900">{r.station_id}</span> },
    { key: 'station_name', header: 'Station Name', render: (r) => <span className="font-semibold text-slate-800">{r.station_name || '-'}</span> },
    { key: 'avg_availability_rate', header: 'Availability Rate', align: 'right', render: (r) => formatPercent(r.avg_availability_rate) },
    { key: 'avg_dock_utilization_rate', header: 'Dock Utilization', align: 'right', render: (r) => formatPercent(r.avg_dock_utilization_rate) },
    { key: 'avg_bikes_available', header: 'Avg Bikes', align: 'right', render: (r) => formatNumber(r.avg_bikes_available, 1) },
    { key: 'active_hour_count', header: 'Active Hours', align: 'right', render: (r) => formatNumber(r.active_hour_count) },
  ];

  return (
    <PageContainer
      title={latestSummary.region_name || `Region ${regionId}`}
      description={`Region ID: ${regionId} • Total Stations: ${latestSummary.station_count || 0}`}
      action={
        <div className="flex items-center gap-3">
          <DateFilter value={effectiveDate} onChange={setSummaryDate} />
          <button
            onClick={() => navigate('/regions')}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 text-slate-700 hover:bg-slate-200 transition-colors border border-slate-200"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Back to Regions
          </button>
        </div>
      }
    >
      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
        <KpiCard
          title="Region ID"
          value={regionId}
          subtitle={latestSummary.region_name || 'Active Region'}
          icon={Compass}
        />
        <KpiCard
          title="Active Stations"
          value={formatNumber(latestSummary.active_station_count)}
          subtitle={`Out of ${formatNumber(latestSummary.station_count)} stations`}
          icon={MapPin}
        />
        <KpiCard
          title="Avg Availability Rate"
          value={formatPercent(latestSummary.avg_availability_rate)}
          subtitle="Region bike availability"
          icon={Bike}
        />
        <KpiCard
          title="Avg Dock Utilization"
          value={formatPercent(latestSummary.avg_dock_utilization_rate)}
          subtitle="Region dock occupancy"
          icon={Layers}
        />
      </div>

      {/* Daily Region Trend Chart */}
      {dailyTrendData.length > 1 && (
        <div className="mb-8">
          <LineChartCard
            title="Daily Region Availability & Utilization Trend (%)"
            subtitle="Historical regional performance over time"
            data={dailyTrendData}
            xAxisKey="date"
            series={[
              { key: 'availabilityRate', name: 'Availability Rate (%)', color: '#16a34a' },
              { key: 'dockUtilization', name: 'Dock Utilization (%)', color: '#0284c7' },
            ]}
            valueFormatter={(v) => `${v.toFixed(1)}%`}
          />
        </div>
      )}

      {/* Region Stations Table */}
      <div>
        <SectionTitle
          title={`Stations in Region (${regionStations.length})`}
          subtitle="Click any station row to view detailed station availability."
        />
        <DataTable
          columns={stationColumns}
          data={regionStations}
          keyExtractor={(row) => `${row.station_id}-${row.summary_date}`}
          onRowClick={(row) => navigate(`/stations/${row.station_id}`)}
        />
      </div>
    </PageContainer>
  );
};

export default RegionDetailPage;
