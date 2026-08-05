import { useQuery } from '@tanstack/react-query';
import pipelineApi from '../api/pipelineApi';
import { PipelineHealthStatus } from '../types/pipeline';

export function useLatestPipelineHealth() {
  return useQuery({
    queryKey: ['latestPipelineHealth'],
    queryFn: () => pipelineApi.getLatestPipelineHealth(),
    staleTime: 30000,
    refetchInterval: 60000,
  });
}

export function usePipelineHealthByStatus(status: PipelineHealthStatus) {
  return useQuery({
    queryKey: ['pipelineHealthByStatus', status],
    queryFn: () => pipelineApi.getPipelineHealthByStatus(status),
    staleTime: 30000,
  });
}

export function usePipelineHealthByDagId(dagId: string) {
  return useQuery({
    queryKey: ['pipelineHealthByDagId', dagId],
    queryFn: () => pipelineApi.getPipelineHealthByDagId(dagId),
    enabled: Boolean(dagId),
    staleTime: 30000,
  });
}

export function useLatestPipelineRuns(limit: number = 20) {
  return useQuery({
    queryKey: ['latestPipelineRuns', limit],
    queryFn: () => pipelineApi.getLatestPipelineRuns(limit),
    staleTime: 30000,
  });
}
