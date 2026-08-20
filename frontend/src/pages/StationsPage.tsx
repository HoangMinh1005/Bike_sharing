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
import { useStationSearch, useStationsDaily } from '../hooks/useStations';
import { useSystemLatest } from '../hooks/useSystem';
import { formatNumber, formatPercent } from '../utils/format';
import { parseApiError } from '../utils/error';
import { StationDailySummary, StationMetadata } from '../types/station';
import { Search, MapPin } from 'lucide-react';

export const StationsPage: React.FC = () => {
  const navigate = useNavigate();
  const [summaryDate, setSummaryDate] = useState<string>('');
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [sortBy, setSortBy] = useState<string>('avg_availability_rate');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  const { data: latestRes } = useSystemLatest();
  const latestDate = latestRes?.data?.summary_date;
  const effectiveDate = summaryDate || latestDate || '';

  const {
    data: stationsRes,
    isLoading,
    isError,
    error,
    refetch,
  } = useStationsDaily(
    effectiveDate
      ? {
          summary_date: effectiveDate,
          sort_by: sortBy,
          sort_order: sortOrder,
          limit: 100,
        }
      : undefined
  );

  const { data: searchRes, isLoading: isSearchLoading } = useStationSearch(searchTerm, 10);

  const stations = stationsRes?.data || [];
  const searchResults = searchRes?.data || [];
  const parsedError = isError ? parseApiError(error, 'No station summary records found for this date.') : null;

  // Top 10 stations for chart
  const top10Stations = [...stations]
    .sort((a, b) => (b.avg_availability_rate || 0) - (a.avg_availability_rate || 0))
    .slice(0, 10)
    .map((s) => ({
      name: s.station_name ? (s.station_name.length > 15 ? s.station_name.substring(0, 15) + '...' : s.station_name) : s.station_id,
      availabilityRate: s.avg_availability_rate ? s.avg_availability_rate * 100 : 0,
      bikesAvailable: s.avg_bikes_available || 0,
    }));

  const tableColumns: Column<StationDailySummary>[] = [
    { key: 'station_id', header: 'Station ID', render: (r) => <span className="font-mono font-medium text-slate-900">{r.station_id}</span> },
    {
      key: 'station_name',
      header: 'Station Name',
      render: (r) => (
        <span className="font-semibold text-slate-800 group-hover:text-indigo-600 transition-colors">
          {r.station_name || '-'}
        </span>
      ),
    },
    { key: 'region_name', header: 'Region', render: (r) => r.region_name || r.region_id || '-' },
    { key: 'avg_bikes_available', header: 'Avg Bikes', align: 'right', render: (r) => formatNumber(r.avg_bikes_available, 1) },
    { key: 'avg_docks_available', header: 'Avg Docks', align: 'right', render: (r) => formatNumber(r.avg_docks_available, 1) },
    { key: 'avg_availability_rate', header: 'Availability Rate', align: 'right', render: (r) => formatPercent(r.avg_availability_rate) },
    { key: 'avg_dock_utilization_rate', header: 'Dock Utilization', align: 'right', render: (r) => formatPercent(r.avg_dock_utilization_rate) },
    { key: 'active_hour_count', header: 'Active Hours', align: 'right', render: (r) => formatNumber(r.active_hour_count) },
  ];

  return (
    <PageContainer
      title="Stations Availability"
      description="Station-level daily availability summaries, search, and capacity monitoring"
      action={<DateFilter value={effectiveDate} onChange={setSummaryDate} />}
    >
      {/* Search & Sort Controls */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs mb-8 space-y-4">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          {/* Station Search Input */}
          <div className="relative flex-1 w-full">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search station by name or short name..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-300 rounded-lg text-xs font-medium text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:bg-white"
            />
          </div>

          {/* Sort By & Order Selectors */}
          <div className="flex items-center space-x-3 shrink-0">
            <div className="flex items-center space-x-2">
              <label className="text-xs font-semibold text-slate-600">Sort By:</label>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="px-3 py-1.5 bg-white border border-slate-300 rounded-lg text-xs font-medium text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              >
                <option value="avg_availability_rate">Availability Rate</option>
                <option value="active_hour_count">Active Hours</option>
                <option value="high_demand_hour_count">High Demand Hours</option>
                <option value="station_id">Station ID</option>
              </select>
            </div>

            <div className="flex items-center space-x-2">
              <label className="text-xs font-semibold text-slate-600">Order:</label>
              <select
                value={sortOrder}
                onChange={(e) => setSortOrder(e.target.value as 'asc' | 'desc')}
                className="px-3 py-1.5 bg-white border border-slate-300 rounded-lg text-xs font-medium text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              >
                <option value="desc">DESC (Giảm dần)</option>
                <option value="asc">ASC (Tăng dần)</option>
              </select>
            </div>
          </div>
        </div>

        {/* Search Results Dropdown List */}
        {searchTerm.trim().length >= 2 && (
          <div className="pt-3 border-t border-slate-100">
            <p className="text-xs font-semibold text-slate-500 mb-2">Search Results:</p>
            {isSearchLoading ? (
              <p className="text-xs text-slate-400">Searching stations...</p>
            ) : searchResults.length === 0 ? (
              <p className="text-xs text-slate-500">No stations matched your search "{searchTerm}"</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                {searchResults.map((st: StationMetadata) => (
                  <button
                    key={st.station_id}
                    onClick={() => navigate(`/stations/${st.station_id}`)}
                    className="flex items-center gap-2 p-2 rounded-lg border border-slate-200 hover:border-emerald-500 hover:bg-emerald-50/50 text-left transition-colors"
                  >
                    <MapPin className="w-4 h-4 text-emerald-600 shrink-0" />
                    <div className="truncate">
                      <p className="text-xs font-semibold text-slate-800 truncate">{st.station_name || st.station_id}</p>
                      <p className="text-[10px] text-slate-400 font-mono">{st.station_id}</p>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Top Stations Chart */}
      {top10Stations.length > 0 && (
        <div className="mb-8">
          <BarChartCard
            title="Top Stations by Availability Rate (%)"
            subtitle="Top performing stations for current summary view"
            data={top10Stations}
            xAxisKey="name"
            series={[{ key: 'availabilityRate', name: 'Availability Rate (%)', color: '#16a34a' }]}
            valueFormatter={(v) => `${v.toFixed(1)}%`}
          />
        </div>
      )}

      {/* Main Table or States */}
      {isLoading ? (
        <LoadingState title="Loading Station Data" message="Fetching station availability metrics..." />
      ) : isError && parsedError ? (
        <ErrorState
          title={parsedError.title}
          message={parsedError.message}
          severity={parsedError.severity}
          technicalDetails={parsedError.technicalDetails}
          actionLabel="Retry"
          onRetry={refetch}
        />
      ) : stations.length === 0 ? (
        <EmptyState
          title="No station data available yet"
          message="The GBFS pipeline is ingesting real-time data, but station summaries have not been recorded for this date yet."
          actionLabel="Refresh Stations"
          onAction={refetch}
        />
      ) : (
        <div>
          <SectionTitle
            title="Station Summaries"
            subtitle={`Showing ${stations.length} stations. Click any row to view detail.`}
          />
          <DataTable
            columns={tableColumns}
            data={stations}
            keyExtractor={(row) => `${row.station_id}-${row.summary_date}`}
            onRowClick={(row) => navigate(`/stations/${row.station_id}`)}
            pageSize={25}
          />
        </div>
      )}
    </PageContainer>
  );
};

export default StationsPage;
