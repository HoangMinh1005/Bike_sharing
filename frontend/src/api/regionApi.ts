import apiClient from './client';
import { ApiListResponse, DateRangeParams, PaginationParams, RegionDailyQueryParams } from '../types/common';
import { RegionDailySummary } from '../types/region';
import { StationDailySummary } from '../types/station';

export const regionApi = {
  getRegionsDaily: async (params?: RegionDailyQueryParams): Promise<ApiListResponse<RegionDailySummary>> => {
    const res = await apiClient.get<ApiListResponse<RegionDailySummary>>('/regions/daily', { params });
    return res.data;
  },

  getRegionDaily: async (regionId: string, params?: DateRangeParams): Promise<ApiListResponse<RegionDailySummary>> => {
    const res = await apiClient.get<ApiListResponse<RegionDailySummary>>(`/regions/${regionId}/daily`, { params });
    return res.data;
  },

  getRegionStations: async (regionId: string, params?: DateRangeParams & PaginationParams & { summary_date?: string }): Promise<ApiListResponse<StationDailySummary>> => {
    const res = await apiClient.get<ApiListResponse<StationDailySummary>>(`/regions/${regionId}/stations`, { params });
    return res.data;
  },
};

export default regionApi;
