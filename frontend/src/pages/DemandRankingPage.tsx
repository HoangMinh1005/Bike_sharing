import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import PageContainer from '../components/layout/PageContainer';
import KpiCard from '../components/common/KpiCard';
import SectionTitle from '../components/common/SectionTitle';
import LoadingState from '../components/common/LoadingState';
import ErrorState from '../components/common/ErrorState';
import StatusBadge from '../components/common/StatusBadge';
import DateFilter from '../components/common/DateFilter';
import BarChartCard from '../components/charts/BarChartCard';
import DonutChartCard from '../components/charts/DonutChartCard';
import DataTable, { Column } from '../components/table/DataTable';
import { useStationRanking, useTopDemandStations } from '../hooks/useRanking';
import { useSystemLatest } from '../hooks/useSystem';
import { formatNumber, formatPercent } from '../utils/format';
import { StationDemandRanking } from '../types/ranking';
import { TrendingUp, Flame, AlertCircle, Award } from 'lucide-react';

export const DemandRankingPage: React.FC = () => {
  const navigate = useNavigate();
  const [rankingDate, setRankingDate] = useState<string>('');
  const [demandCategory, setDemandCategory] = useState<'ALL' | 'HIGH' | 'MEDIUM' | 'LOW'>('ALL');

  const { data: latestRes } = useSystemLatest();
  const latestDate = latestRes?.data?.summary_date;
  const effectiveDate = rankingDate || latestDate || '';

  // Fetch all rankings for date (without category filter and without top_n limit) to compute accurate KPI card counts
  const { data: allRankingsRes } = useStationRanking({
    ranking_date: effectiveDate,
  });

  // Fetch filtered rankings based on selected category button
  const { data: rankingRes, isLoading, isError, refetch } = useStationRanking({
    ranking_date: effectiveDate,
    demand_category: demandCategory === 'ALL' ? undefined : demandCategory,
  });

  const { data: topDemandRes } = useTopDemandStations({
    ranking_date: effectiveDate,
    top_n: 5,
  });

  const rankings = rankingRes?.data || [];
  const allRankings = allRankingsRes?.data || rankings;
  const top5Stations = topDemandRes?.data || [];

  // Summary counts by demand category
  const highCount = allRankings.filter((r) => r.demand_category === 'HIGH').length;
  const mediumCount = allRankings.filter((r) => r.demand_category === 'MEDIUM').length;
  const lowCount = allRankings.filter((r) => r.demand_category === 'LOW').length;

  // Chart data
  const top10BarData = rankings
    .slice(0, 10)
    .map((r) => ({
      name: r.station_name ? (r.station_name.length > 15 ? r.station_name.substring(0, 15) + '...' : r.station_name) : r.station_id,
      score: r.demand_score || 0,
    }));

  const categoryDonutData = [
    { name: 'High Demand', value: highCount, color: '#f43f5e' },
    { name: 'Medium Demand', value: mediumCount, color: '#f59e0b' },
    { name: 'Low Demand', value: lowCount, color: '#10b981' },
  ];

  const tableColumns: Column<StationDemandRanking>[] = [
    { key: 'demand_rank', header: 'Rank', align: 'center', render: (r) => <span className="font-bold text-slate-900">#{r.demand_rank}</span> },
    { key: 'station_id', header: 'Station ID', render: (r) => <span className="font-mono font-medium text-slate-900">{r.station_id}</span> },
    { key: 'station_name', header: 'Station Name', render: (r) => <span className="font-semibold text-slate-800">{r.station_name || '-'}</span> },
    { key: 'region_name', header: 'Region', render: (r) => r.region_name || r.region_id || '-' },
    { key: 'demand_category', header: 'Category', align: 'center', render: (r) => <StatusBadge status={r.demand_category} type="demand" /> },
    { key: 'demand_score', header: 'Demand Score', align: 'right', render: (r) => formatNumber(r.demand_score, 2) },
    { key: 'low_availability_hour_count', header: 'Low Avail Hours', align: 'right', render: (r) => formatNumber(r.low_availability_hour_count) },
    { key: 'empty_hour_count', header: 'Empty Hours', align: 'right', render: (r) => formatNumber(r.empty_hour_count) },
    { key: 'avg_availability_rate', header: 'Avg Avail Rate', align: 'right', render: (r) => formatPercent(r.avg_availability_rate) },
  ];

  return (
    <PageContainer
      title="Station Demand Ranking"
      description="Station demand classification, high-demand hot-spot identification, and availability metrics"
      action={<DateFilter value={effectiveDate} onChange={setRankingDate} />}
    >
      {/* Category Filter Controls */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm mb-8 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center space-x-2">
          <span className="text-xs font-semibold text-slate-600">Category Filter:</span>
          {(['ALL', 'HIGH', 'MEDIUM', 'LOW'] as const).map((cat) => (
            <button
              key={cat}
              onClick={() => setDemandCategory(cat)}
              className={`px-3 py-1 rounded-lg text-xs font-semibold transition-colors ${
                demandCategory === cat
                  ? 'bg-slate-900 text-white shadow-xs'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
        <span className="text-xs text-slate-500 font-medium">Total Ranked: {rankings.length} stations</span>
      </div>

      {/* Top Category KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
        <KpiCard
          title="Total Ranked Stations"
          value={formatNumber(rankings.length)}
          subtitle="Assessed stations"
          icon={TrendingUp}
        />
        <KpiCard
          title="High Demand Stations"
          value={formatNumber(highCount)}
          subtitle="Critical rebalancing priority"
          status="HIGH"
          badgeType="demand"
          icon={Flame}
        />
        <KpiCard
          title="Medium Demand Stations"
          value={formatNumber(mediumCount)}
          subtitle="Moderate station usage"
          status="MEDIUM"
          badgeType="demand"
          icon={AlertCircle}
        />
        <KpiCard
          title="Low Demand Stations"
          value={formatNumber(lowCount)}
          subtitle="Normal availability"
          status="LOW"
          badgeType="demand"
          icon={Award}
        />
      </div>

      {/* Top 5 High Demand Spotlight Cards */}
      {top5Stations.length > 0 && (
        <div className="mb-8">
          <SectionTitle title="Top 5 High Demand Stations" subtitle="Stations requiring urgent operational attention" />
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            {top5Stations.map((st) => (
              <div
                key={st.station_id}
                onClick={() => navigate(`/stations/${st.station_id}`)}
                className="bg-white rounded-xl border border-rose-200 p-4 shadow-xs hover:shadow-md cursor-pointer transition-all border-l-4 border-l-rose-500"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-rose-600">Rank #{st.demand_rank}</span>
                  <StatusBadge status={st.demand_category} type="demand" />
                </div>
                <h4 className="text-xs font-bold text-slate-900 truncate mb-1" title={st.station_name}>
                  {st.station_name || st.station_id}
                </h4>
                <p className="text-[10px] text-slate-500 mb-3 truncate">{st.region_name || st.region_id || 'Region N/A'}</p>
                <div className="space-y-1 text-[11px] pt-2 border-t border-slate-100">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Demand Score:</span>
                    <span className="font-bold text-slate-800">{formatNumber(st.demand_score, 2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Empty Hours:</span>
                    <span className="font-semibold text-rose-600">{formatNumber(st.empty_hour_count)}h</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Demand Charts */}
      {top10BarData.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          <BarChartCard
            title="Top 10 Stations by Demand Score"
            subtitle="Calculated composite demand metric"
            data={top10BarData}
            xAxisKey="name"
            series={[{ key: 'score', name: 'Demand Score', color: '#f43f5e' }]}
            valueFormatter={(v) => v.toFixed(2)}
          />

          <DonutChartCard
            title="Demand Category Distribution"
            subtitle="Breakdown by demand status category"
            data={categoryDonutData}
          />
        </div>
      )}

      {/* Main Ranking Table */}
      {isLoading ? (
        <LoadingState message="Loading station demand rankings..." />
      ) : isError ? (
        <ErrorState message="Could not load demand ranking data." onRetry={refetch} />
      ) : (
        <div>
          <SectionTitle
            title="Station Demand Rankings Table"
            subtitle="Click any row to view individual station availability detail."
          />
          <DataTable
            columns={tableColumns}
            data={rankings}
            keyExtractor={(row) => `${row.station_id}-${row.ranking_date}`}
            onRowClick={(row) => navigate(`/stations/${row.station_id}`)}
            pageSize={25}
          />
        </div>
      )}
    </PageContainer>
  );
};

export default DemandRankingPage;
