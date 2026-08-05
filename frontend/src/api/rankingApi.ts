import apiClient from './client';
import { ApiDataResponse, ApiListResponse, RankingQueryParams } from '../types/common';
import { StationDemandRanking } from '../types/ranking';

export const rankingApi = {
  getStationRanking: async (params?: RankingQueryParams): Promise<ApiListResponse<StationDemandRanking>> => {
    const res = await apiClient.get<ApiListResponse<StationDemandRanking>>('/ranking/stations', { params });
    return res.data;
  },

  getTopDemandStations: async (params?: RankingQueryParams): Promise<ApiListResponse<StationDemandRanking>> => {
    const res = await apiClient.get<ApiListResponse<StationDemandRanking>>('/ranking/stations/top-demand', { params });
    return res.data;
  },

  getStationRankingDetail: async (stationId: string, rankingDate?: string): Promise<ApiDataResponse<StationDemandRanking>> => {
    const res = await apiClient.get<ApiDataResponse<StationDemandRanking>>(`/ranking/stations/${stationId}`, {
      params: rankingDate ? { ranking_date: rankingDate } : undefined,
    });
    return res.data;
  },
};

export default rankingApi;
