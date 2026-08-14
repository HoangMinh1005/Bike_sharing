import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import PageContainer from '../components/layout/PageContainer';
import KpiCard from '../components/common/KpiCard';
import SectionTitle from '../components/common/SectionTitle';
import LoadingState from '../components/common/LoadingState';
import ErrorState from '../components/common/ErrorState';
import EmptyState from '../components/common/EmptyState';
import StatusBadge from '../components/common/StatusBadge';
import DateFilter from '../components/common/DateFilter';
import BarChartCard from '../components/charts/BarChartCard';
import DonutChartCard from '../components/charts/DonutChartCard';
import DataTable, { Column } from '../components/table/DataTable';
import { useStationRanking, useTopDemandStations } from '../hooks/useRanking';
import { useSystemLatest } from '../hooks/useSystem';
import { formatNumber, formatPercent } from '../utils/format';
import { parseApiError } from '../utils/error';
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
  const { data: rankingRes, isLoading, isError, error, refetch } = useStationRanking({
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
  const parsedError = isError ? parseApiError(error, 'No demand ranking data found for this date.') : null;

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
    {
      key: 'demand_rank',
      header: 'Rank',
      align: 'center',
      render: (r) => (
        <span
          className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold ${
            r.demand_rank === 1
              ? 'bg-amber-100 text-amber-800'
              : r.demand_rank === 2
              ? 'bg-slate-200 text-slate-800'
              : r.demand_rank === 3
              ? 'bg-amber-700/20 text-amber-900'
              : 'text-slate-600'
          }`}
        >
          {r.demand_rank}
        </span>
      ),
    },
    { key: 'station_id', header: 'Station ID', render: (r) => <span className="font-mono font-medium text-slate-900">{r.station_id}</span> },
    { key: 'station_name', header: 'Station Name', render: (r) => <span className="font-semibold text-slate-800">{r.station_name || '-'}</span> },
    { key: 'region_name', header: 'Region', render: (r) => r.region_name || r.region_id || '-' },
    {
      key: 'demand_category',
      header: 'Demand Category',
      align: 'center',
      render: (r) => <StatusBadge status={r.demand_category} type="demand" />,
    },
    { key: 'demand_score', header: 'Demand Score', align: 'right', render: (r) => <span className="font-bold text-rose-600">{formatNumber(r.demand_score, 2)}</span> },
    { key: 'avg_availability_rate', header: 'Availability Rate', align: 'right', render: (r) => formatPercent(r.avg_availability_rate) },
    { key: 'empty_hour_count', header: 'Empty Hours', align: 'right', render: (r) => formatNumber(r.empty_hour_count) },
    { key: 'high_demand_hour_count', header: 'High-Demand Hours', align: 'right', render: (r) => formatNumber(r.high_demand_hour_count) },
  ];

  return (
    <PageContainer
      title="Station Demand Ranking"
      description="Daily station demand score calculation and rebalancing urgency ranking"
      action={<DateFilter value={effectiveDate} onChange={setRankingDate} />}
    >
      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
        <KpiCard
          title="Total Ranked Stations"
          value={formatNumber(allRankings.length)}
          subtitle="Stations with demand score"
          icon={TrendingUp}
        />
        <KpiCard
          title="High Demand Stations"
          value={formatNumber(highCount)}
          subtitle="Top urgency rebalancing target"
          icon={Flame}
          status="HIGH"
          badgeType="demand"
        />
        <KpiCard
          title="Medium Demand Stations"
          value={formatNumber(mediumCount)}
          subtitle="Moderate shortage frequency"
          icon={AlertCircle}
          status="MEDIUM"
          badgeType="demand"
        />
        <KpiCard
          title="Low Demand / Balanced"
          value={formatNumber(lowCount)}
          subtitle="Adequate inventory balance"
          icon={Award}
          status="BALANCED"
          badgeType="demand"
        />
      </div>

      {/* Top 5 Urgent Rebalance Targets */}
      {top5Stations.length > 0 && (
        <div className="bg-rose-50/50 border border-rose-200 rounded-xl p-5 mb-8">
          <SectionTitle
            title="Top 5 High-Demand Hotspots"
            subtitle="Stations requiring immediate rebalancing intervention"
          />
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-3 mt-3">
            {top5Stations.map((st) => (
              <button
                key={st.station_id}
                onClick={() => navigate(`/stations/${st.station_id}`)}
                className="bg-white border border-rose-200 rounded-lg p-3 text-left hover:border-rose-400 hover:shadow-xs transition-all"
              >
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-rose-100 text-rose-800">
                  Rank #{st.demand_rank}
                </span>
                <p className="text-xs font-bold text-slate-900 truncate mt-1">{st.station_name || st.station_id}</p>
                <div className="flex justify-between items-center mt-2 text-[11px] text-slate-500">
                  <span>Score: <strong className="text-rose-600">{st.demand_score?.toFixed(2)}</strong></span>
                  <span>Empty: <strong>{st.empty_hour_count}h</strong></span>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Category Filter Tabs */}
      <div className="flex items-center gap-2 mb-6 border-b border-slate-200 pb-3">
        {(['ALL', 'HIGH', 'MEDIUM', 'LOW'] as const).map((cat) => (
          <button
            key={cat}
            onClick={() => setDemandCategory(cat)}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition-colors ${
              demandCategory === cat
                ? 'bg-slate-900 text-white shadow-xs'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            {cat === 'ALL' ? `All (${allRankings.length})` : `${cat} (${cat === 'HIGH' ? highCount : cat === 'MEDIUM' ? mediumCount : lowCount})`}
          </button>
        ))}
      </div>

      {/* Charts Section */}
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

      {/* Main Ranking Table or States */}
      {isLoading ? (
        <LoadingState title="Loading Demand Rankings" message="Computing demand scores and ranking stations..." />
      ) : isError && parsedError ? (
        <ErrorState
          title={parsedError.title}
          message={parsedError.message}
          severity={parsedError.severity}
          technicalDetails={parsedError.technicalDetails}
          actionLabel="Retry"
          onRetry={refetch}
        />
      ) : rankings.length === 0 ? (
        <EmptyState
          title="Demand ranking is not ready yet"
          message="Station demand scoring requires sufficient hourly availability observations for the target ranking date."
          actionLabel="Refresh Rankings"
          onAction={refetch}
        />
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
