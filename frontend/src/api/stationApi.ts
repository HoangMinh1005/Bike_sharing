import apiClient from './client';
import { ApiListResponse, DateRangeParams, DateTimeRangeParams, PaginationParams, StationDailyQueryParams } from '../types/common';
import { StationDailySummary, StationHourlyAvailability, StationMetadata } from '../types/station';

export const stationApi = {
  getStationsDaily: async (params?: StationDailyQueryParams): Promise<ApiListResponse<StationDailySummary>> => {
    const res = await apiClient.get<ApiListResponse<StationDailySummary>>('/stations/daily', { params });
    return res.data;
  },

  searchStations: async (q: string, limit: number = 10): Promise<ApiListResponse<StationMetadata>> => {
    const res = await apiClient.get<ApiListResponse<StationMetadata>>('/stations/search', {
      params: { q, limit },
    });
    return res.data;
  },

  getStationDaily: async (stationId: string, params?: DateRangeParams): Promise<ApiListResponse<StationDailySummary>> => {
    const res = await apiClient.get<ApiListResponse<StationDailySummary>>(`/stations/${stationId}/daily`, { params });
    return res.data;
  },

  getStationHourly: async (stationId: string, params?: DateTimeRangeParams & PaginationParams): Promise<ApiListResponse<StationHourlyAvailability>> => {
    const res = await apiClient.get<ApiListResponse<StationHourlyAvailability>>(`/stations/${stationId}/hourly`, { params });
    return res.data;
  },
};

export default stationApi;
