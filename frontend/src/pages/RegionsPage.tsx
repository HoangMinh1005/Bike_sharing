import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import PageContainer from '../components/layout/PageContainer';
import SectionTitle from '../components/common/SectionTitle';
import LoadingState from '../components/common/LoadingState';
import ErrorState from '../components/common/ErrorState';
import EmptyState from '../components/common/EmptyState';
import DateFilter from '../components/common/DateFilter';
import BarChartCard from '../components/charts/BarChartCard';
import DataTable, { Column } from '../components/table/DataTable';
import { useRegionsDaily } from '../hooks/useRegions';
import { useSystemLatest } from '../hooks/useSystem';
import { formatNumber, formatPercent } from '../utils/format';
import { parseApiError } from '../utils/error';
import { RegionDailySummary } from '../types/region';

export const RegionsPage: React.FC = () => {
  const navigate = useNavigate();
  const [summaryDate, setSummaryDate] = useState<string>('');

  const { data: latestRes } = useSystemLatest();
  const latestDate = latestRes?.data?.summary_date;
  const effectiveDate = summaryDate || latestDate || '';

  const { data: regionsRes, isLoading, isError, error, refetch } = useRegionsDaily({
    summary_date: effectiveDate,
  });

  const regions = regionsRes?.data || [];
  const parsedError = isError ? parseApiError(error, 'No region summary records found for this date.') : null;

  // Chart data
  const regionChartData = regions.map((r) => ({
    name: r.region_name || r.region_id,
    availabilityRate: r.avg_availability_rate ? r.avg_availability_rate * 100 : 0,
    activeStations: r.active_station_count || 0,
  }));

  const tableColumns: Column<RegionDailySummary>[] = [
    { key: 'region_id', header: 'Region ID', render: (r) => <span className="font-mono font-medium text-slate-900">{r.region_id}</span> },
    { key: 'region_name', header: 'Region Name', render: (r) => <span className="font-semibold text-slate-800">{r.region_name || '-'}</span> },
    { key: 'station_count', header: 'Total Stations', align: 'right', render: (r) => formatNumber(r.station_count) },
    { key: 'active_station_count', header: 'Active Stations', align: 'right', render: (r) => formatNumber(r.active_station_count) },
    { key: 'avg_availability_rate', header: 'Availability Rate', align: 'right', render: (r) => formatPercent(r.avg_availability_rate) },
    { key: 'avg_dock_utilization_rate', header: 'Dock Utilization', align: 'right', render: (r) => formatPercent(r.avg_dock_utilization_rate) },
    { key: 'high_demand_station_count', header: 'High Demand Stations', align: 'right', render: (r) => formatNumber(r.high_demand_station_count) },
  ];

  return (
    <PageContainer
      title="Regions Summary"
      description="Regional breakdown of station distribution, availability rates, and regional demand"
      action={<DateFilter value={effectiveDate} onChange={setSummaryDate} />}
    >
      {/* Region Charts */}
      {regionChartData.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          <BarChartCard
            title="Avg Availability Rate by Region (%)"
            subtitle="Regional performance comparison"
            data={regionChartData}
            xAxisKey="name"
            series={[{ key: 'availabilityRate', name: 'Availability Rate (%)', color: '#16a34a' }]}
            valueFormatter={(v) => `${v.toFixed(1)}%`}
          />

          <BarChartCard
            title="Active Station Count by Region"
            subtitle="Regional station deployment"
            data={regionChartData}
            xAxisKey="name"
            series={[{ key: 'activeStations', name: 'Active Stations', color: '#0284c7' }]}
            valueFormatter={(v) => formatNumber(v)}
          />
        </div>
      )}

      {/* Main Table or States */}
      {isLoading ? (
        <LoadingState title="Loading Region Summaries" message="Fetching regional availability metrics..." />
      ) : isError && parsedError ? (
        <ErrorState
          title={parsedError.title}
          message={parsedError.message}
          severity={parsedError.severity}
          technicalDetails={parsedError.technicalDetails}
          actionLabel="Retry"
          onRetry={refetch}
        />
      ) : regions.length === 0 ? (
        <EmptyState
          title="No region summary available yet"
          message="Region-level aggregations will appear after the station and region metadata pipelines complete."
          actionLabel="Refresh Regions"
          onAction={refetch}
        />
      ) : (
        <div>
          <SectionTitle
            title="Region Summaries"
            subtitle={`Showing ${regions.length} regions. Click any row to view detail.`}
          />
          <DataTable
            columns={tableColumns}
            data={regions}
            keyExtractor={(row) => `${row.region_id}-${row.summary_date}`}
            onRowClick={(row) => navigate(`/regions/${row.region_id}`)}
          />
        </div>
      )}
    </PageContainer>
  );
};

export default RegionsPage;
