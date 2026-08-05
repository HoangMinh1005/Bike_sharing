import apiClient from './client';
import { ApiDataResponse, ApiListResponse } from '../types/common';
import { PipelineHealth, PipelineHealthStatus, PipelineRun } from '../types/pipeline';

export const pipelineApi = {
  getLatestPipelineHealth: async (): Promise<ApiListResponse<PipelineHealth>> => {
    const res = await apiClient.get<ApiListResponse<PipelineHealth>>('/pipelines/health/latest');
    return res.data;
  },

  getPipelineHealthByStatus: async (status: PipelineHealthStatus): Promise<ApiListResponse<PipelineHealth>> => {
    const res = await apiClient.get<ApiListResponse<PipelineHealth>>(`/pipelines/health/status/${status}`);
    return res.data;
  },

  getPipelineHealthByDagId: async (dagId: string): Promise<ApiDataResponse<PipelineHealth>> => {
    const res = await apiClient.get<ApiDataResponse<PipelineHealth>>(`/pipelines/health/${dagId}`);
    return res.data;
  },

  getLatestPipelineRuns: async (limit: number = 20): Promise<ApiListResponse<PipelineRun>> => {
    const res = await apiClient.get<ApiListResponse<PipelineRun>>('/pipelines/runs/latest', {
      params: { limit },
    });
    return res.data;
  },
};

export default pipelineApi;
