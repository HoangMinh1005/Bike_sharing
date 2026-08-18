import apiClient from './client';
import { ApiDataResponse, ApiListResponse } from '../types/common';
import { AlertEvent, AlertStats } from '../types/alert';

export const alertApi = {
  getStats: async (): Promise<ApiDataResponse<AlertStats>> => {
    const res = await apiClient.get<ApiDataResponse<AlertStats>>('/alerts/stats');
    return res.data;
  },

  getLatest: async (limit: number = 20): Promise<ApiDataResponse<AlertEvent[]>> => {
    const res = await apiClient.get<ApiDataResponse<AlertEvent[]>>('/alerts/latest', {
      params: { limit },
    });
    return res.data;
  },

  getActive: async (limit: number = 50): Promise<ApiDataResponse<AlertEvent[]>> => {
    const res = await apiClient.get<ApiDataResponse<AlertEvent[]>>('/alerts/active', {
      params: { limit },
    });
    return res.data;
  },

  getHistory: async (params: {
    limit?: number;
    offset?: number;
    severity?: string;
    status?: string;
    alert_type?: string;
    dag_id?: string;
    sort_by?: string;
    sort_order?: string;
  }): Promise<ApiListResponse<AlertEvent>> => {
    const res = await apiClient.get<ApiListResponse<AlertEvent>>('/alerts/history', {
      params,
    });
    return res.data;
  },
};
