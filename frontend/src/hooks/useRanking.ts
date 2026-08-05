import { useQuery } from '@tanstack/react-query';
import rankingApi from '../api/rankingApi';
import { RankingQueryParams } from '../types/common';

export function useStationRanking(params?: RankingQueryParams) {
  return useQuery({
    queryKey: ['stationRanking', params],
    queryFn: () => rankingApi.getStationRanking(params),
    enabled: Boolean(params?.ranking_date),
    staleTime: 60000,
  });
}

export function useTopDemandStations(params?: RankingQueryParams) {
  return useQuery({
    queryKey: ['topDemandStations', params],
    queryFn: () => rankingApi.getTopDemandStations(params),
    enabled: Boolean(params?.ranking_date),
    staleTime: 60000,
  });
}

export function useStationRankingDetail(stationId: string, rankingDate?: string) {
  return useQuery({
    queryKey: ['stationRankingDetail', stationId, rankingDate],
    queryFn: () => rankingApi.getStationRankingDetail(stationId, rankingDate),
    enabled: Boolean(stationId),
    staleTime: 60000,
  });
}
