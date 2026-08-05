import { useQuery } from '@tanstack/react-query';
import stationApi from '../api/stationApi';
import { DateRangeParams, DateTimeRangeParams, PaginationParams, StationDailyQueryParams } from '../types/common';

export function useStationsDaily(params?: StationDailyQueryParams) {
  return useQuery({
    queryKey: ['stationsDaily', params],
    queryFn: () => stationApi.getStationsDaily(params),
    enabled: Boolean(params?.summary_date),
    staleTime: 60000,
  });
}

export function useStationSearch(query: string, limit: number = 10) {
  return useQuery({
    queryKey: ['stationSearch', query, limit],
    queryFn: () => stationApi.searchStations(query, limit),
    enabled: Boolean(query && query.trim().length >= 2),
    staleTime: 60000,
  });
}

export function useStationDaily(stationId: string, params?: DateRangeParams) {
  return useQuery({
    queryKey: ['stationDaily', stationId, params],
    queryFn: () => stationApi.getStationDaily(stationId, params),
    enabled: Boolean(stationId),
    staleTime: 60000,
  });
}

export function useStationHourly(stationId: string, params?: DateTimeRangeParams & PaginationParams) {
  return useQuery({
    queryKey: ['stationHourly', stationId, params],
    queryFn: () => stationApi.getStationHourly(stationId, params),
    enabled: Boolean(stationId),
    staleTime: 60000,
  });
}
