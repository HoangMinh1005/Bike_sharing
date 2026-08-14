import React from 'react';
import PageContainer from '../components/layout/PageContainer';
import KpiCard from '../components/common/KpiCard';
import SectionTitle from '../components/common/SectionTitle';
import LoadingState from '../components/common/LoadingState';
import ErrorState from '../components/common/ErrorState';
import EmptyState from '../components/common/EmptyState';
import StatusBadge from '../components/common/StatusBadge';
import BarChartCard from '../components/charts/BarChartCard';
import DonutChartCard from '../components/charts/DonutChartCard';
import DataTable, { Column } from '../components/table/DataTable';
import { useLatestPipelineHealth, useLatestPipelineRuns } from '../hooks/usePipelines';
import { formatDateTime, formatDurationMinutes, formatNumber } from '../utils/format';
import { parseApiError } from '../utils/error';
import { PipelineHealth, PipelineRun } from '../types/pipeline';
import { Activity, ShieldCheck, AlertTriangle, XCircle, Clock, Info } from 'lucide-react';

export const PipelineHealthPage: React.FC = () => {
  const {
    data: healthRes,
    isLoading: isHealthLoading,
    isError: isHealthError,
    error: healthError,
    refetch: refetchHealth,
  } = useLatestPipelineHealth();
  const { data: runsRes, isLoading: isRunsLoading } = useLatestPipelineRuns(20);

  if (isHealthLoading && isRunsLoading) {
    return (
      <PageContainer title="Pipeline Health Monitoring">
        <LoadingState title="Loading Pipeline Health" message="Fetching DAG health metrics and recent run executions..." />
      </PageContainer>
    );
  }

  const parsedError = isHealthError ? parseApiError(healthError, 'No pipeline health summary records found in metadata.') : null;

  if (parsedError && (parsedError.isNetworkError || parsedError.isServerError)) {
    return (
      <PageContainer title="Pipeline Health Monitoring">
        <ErrorState
          title={parsedError.title}
          message={parsedError.message}
          severity={parsedError.severity}
          technicalDetails={parsedError.technicalDetails}
          actionLabel="Retry"
          onRetry={refetchHealth}
        />
      </PageContainer>
    );
  }

  const pipelines = healthRes?.data || [];
  const recentRuns = runsRes?.data || [];

  if (pipelines.length === 0) {
    return (
      <PageContainer title="Pipeline Health Monitoring">
        <EmptyState
          title="Pipeline health has not been recorded yet"
          message="The pipeline health monitoring DAG (pipeline_health_dag) records execution and data quality metrics every 30 minutes."
          actionLabel="Refresh Health Status"
          onAction={refetchHealth}
        />
      </PageContainer>
    );
  }

  // Summary status counts
  const healthyCount = pipelines.filter((p) => p.health_status === 'HEALTHY').length;
  const warningCount = pipelines.filter((p) => p.health_status === 'WARNING').length;
  const failedCount = pipelines.filter((p) => p.health_status === 'FAILED').length;
  const staleCount = pipelines.filter((p) => p.health_status === 'STALE').length;

  // Chart data
  const freshnessChartData = pipelines.map((p) => ({
    dag: p.monitored_dag_id.replace('_dag', ''),
    lagMinutes: p.freshness_lag_minutes || 0,
    threshold: p.freshness_threshold_minutes || 0,
  }));

  const healthStatusDonutData = [
    { name: 'Healthy', value: healthyCount, color: '#10b981' },
    { name: 'Warning', value: warningCount, color: '#f59e0b' },
    { name: 'Failed', value: failedCount, color: '#f43f5e' },
    { name: 'Stale', value: staleCount, color: '#f97316' },
  ];

  const healthTableColumns: Column<PipelineHealth>[] = [
    { key: 'monitored_dag_id', header: 'DAG ID', render: (r) => <span className="font-mono font-semibold text-slate-900">{r.monitored_dag_id}</span> },
    { key: 'health_status', header: 'Health Status', align: 'center', render: (r) => <StatusBadge status={r.health_status} type="health" /> },
    { key: 'latest_run_status', header: 'Latest Run', align: 'center', render: (r) => <StatusBadge status={r.latest_run_status} type="generic" /> },
    { key: 'freshness_lag_minutes', header: 'Freshness Lag', align: 'right', render: (r) => formatDurationMinutes(r.freshness_lag_minutes) },
    { key: 'dq_failed_checks', header: 'DQ Failed', align: 'right', render: (r) => <span className={r.dq_failed_checks > 0 ? 'text-rose-600 font-bold' : ''}>{formatNumber(r.dq_failed_checks)}</span> },
    { key: 'rejected_record_count', header: 'Rejected Records', align: 'right', render: (r) => formatNumber(r.rejected_record_count) },
    { key: 'latest_success_finished_at', header: 'Latest Success', render: (r) => formatDateTime(r.latest_success_finished_at) },
  ];

  const runsTableColumns: Column<PipelineRun>[] = [
    { key: 'run_id', header: 'Run ID', render: (r) => <span className="font-mono text-xs text-slate-700">{r.run_id}</span> },
    { key: 'dag_id', header: 'DAG ID', render: (r) => <span className="font-mono font-medium text-slate-800">{r.dag_id}</span> },
    { key: 'status', header: 'Status', align: 'center', render: (r) => <StatusBadge status={r.status} type="generic" /> },
    { key: 'started_at', header: 'Started At', render: (r) => formatDateTime(r.started_at) },
    { key: 'ended_at', header: 'Finished At', render: (r) => formatDateTime(r.ended_at) },
    { key: 'records_loaded', header: 'Records Loaded', align: 'right', render: (r) => formatNumber(r.records_loaded) },
    { key: 'records_rejected', header: 'Rejected', align: 'right', render: (r) => formatNumber(r.records_rejected) },
  ];

  return (
    <PageContainer
      title="Pipeline Health Monitoring"
      description="SLA freshness monitoring, automated Data Quality checks, and recent pipeline execution logs"
    >
      {/* Top Health KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
        <KpiCard
          title="Monitored DAGs"
          value={formatNumber(pipelines.length)}
          subtitle="Active pipelines"
          icon={Activity}
        />
        <KpiCard
          title="Healthy Pipelines"
          value={formatNumber(healthyCount)}
          subtitle="Operating within SLA"
          status="HEALTHY"
          badgeType="health"
          icon={ShieldCheck}
        />
        <KpiCard
          title="Warning Pipelines"
          value={formatNumber(warningCount)}
          subtitle="Minor DQ issues"
          status="WARNING"
          badgeType="health"
          icon={AlertTriangle}
        />
        <KpiCard
          title="Failed Pipelines"
          value={formatNumber(failedCount)}
          subtitle="Critical SLA failure"
          status={failedCount > 0 ? 'FAILED' : 'HEALTHY'}
          badgeType="health"
          icon={XCircle}
        />
        <KpiCard
          title="Stale Pipelines"
          value={formatNumber(staleCount)}
          subtitle="Exceeded lag threshold"
          status={staleCount > 0 ? 'STALE' : 'HEALTHY'}
          badgeType="health"
          icon={Clock}
        />
      </div>

      {/* Monitored DAG Status Cards */}
      <div className="mb-8">
        <SectionTitle title="Monitored Pipeline DAG Status" subtitle="Individual SLA lag and Data Quality check summary" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {pipelines.map((p) => (
            <div
              key={p.monitored_dag_id}
              className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs hover:shadow-md transition-shadow"
            >
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-xs font-bold text-slate-900 font-mono">{p.monitored_dag_id}</h4>
                <StatusBadge status={p.health_status} type="health" />
              </div>
              <p className="text-xs text-slate-500 mb-4">{p.health_message || 'Pipeline operational.'}</p>
              <div className="space-y-2 text-xs pt-3 border-t border-slate-100">
                <div className="flex justify-between">
                  <span className="text-slate-500">Freshness Lag:</span>
                  <span className="font-semibold text-slate-800">{formatDurationMinutes(p.freshness_lag_minutes)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">DQ Failed Checks:</span>
                  <span className={`font-semibold ${p.dq_failed_checks > 0 ? 'text-rose-600' : 'text-slate-800'}`}>
                    {p.dq_failed_checks} / {p.dq_total_checks}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Rejected Records:</span>
                  <span className="font-semibold text-slate-800">{formatNumber(p.rejected_record_count)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Latest Finished:</span>
                  <span className="font-medium text-slate-600">{formatDateTime(p.latest_finished_at)}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Data Quality Notes & Known Limitations */}
      <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 mb-8">
        <div className="flex items-start gap-3">
          <Info className="w-5 h-5 text-sky-600 mt-0.5 shrink-0" />
          <div className="space-y-1">
            <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
              Data Quality Notes & Known Data Limitations
            </h4>
            <p className="text-xs text-slate-600">
              • <strong>Station Region Mapping</strong>: Some GBFS feeds omit optional <code className="text-[11px] bg-white px-1 py-0.5 rounded border border-slate-200">region_id</code> fields. Stations with missing or unmapped region IDs are automatically grouped under <strong>Unknown Region</strong> (<code className="text-[11px] bg-white px-1 py-0.5 rounded border border-slate-200">region_id = 'UNKNOWN'</code>).
            </p>
            <p className="text-xs text-slate-600">
              • <strong>Operational Threshold</strong>: Missing region rates under <strong>&le; 1.0%</strong> are marked as accepted non-blocking limitations and do not impact Overall Pipeline Health.
            </p>
          </div>
        </div>
      </div>

      {/* Health Charts */}
      {freshnessChartData.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          <BarChartCard
            title="Freshness Lag Minutes by DAG"
            subtitle="Current data lag against expected schedule threshold"
            data={freshnessChartData}
            xAxisKey="dag"
            series={[
              { key: 'lagMinutes', name: 'Lag (Minutes)', color: '#0284c7' },
              { key: 'threshold', name: 'SLA Threshold', color: '#f59e0b' },
            ]}
            valueFormatter={(v) => formatDurationMinutes(v)}
          />

          <DonutChartCard
            title="Pipeline Health Status Overview"
            subtitle="Distribution of monitored DAG health statuses"
            data={healthStatusDonutData}
          />
        </div>
      )}

      {/* Health Summary Table */}
      <div className="mb-8">
        <SectionTitle title="Pipeline Health Summary Table" subtitle="Comprehensive status overview for monitored pipelines" />
        <DataTable
          columns={healthTableColumns}
          data={pipelines}
          keyExtractor={(row) => row.health_run_id || row.monitored_dag_id}
        />
      </div>

      {/* Recent Pipeline Runs Table */}
      {recentRuns.length > 0 && (
        <div>
          <SectionTitle title="Recent Pipeline Execution Runs" subtitle="Execution logs from etl_metadata.pipeline_runs" />
          <DataTable
            columns={runsTableColumns}
            data={recentRuns}
            keyExtractor={(row) => row.run_id}
          />
        </div>
      )}
    </PageContainer>
  );
};

export default PipelineHealthPage;
