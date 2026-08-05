import apiClient from './client';
import { ApiDataResponse, ApiListResponse, DateRangeParams, PaginationParams } from '../types/common';
import { HourlyMobilitySummary, SystemDailySummary } from '../types/system';

export const systemApi = {
  getSystemLatest: async (): Promise<ApiDataResponse<SystemDailySummary>> => {
    const res = await apiClient.get<ApiDataResponse<SystemDailySummary>>('/system/latest');
    return res.data;
  },

  getSystemDaily: async (params?: DateRangeParams): Promise<ApiListResponse<SystemDailySummary>> => {
    const res = await apiClient.get<ApiListResponse<SystemDailySummary>>('/system/daily', { params });
    return res.data;
  },

  getSystemHourly: async (params?: DateRangeParams & PaginationParams): Promise<ApiListResponse<HourlyMobilitySummary>> => {
    const res = await apiClient.get<ApiListResponse<HourlyMobilitySummary>>('/system/hourly', { params });
    return res.data;
  },
};

export default systemApi;
