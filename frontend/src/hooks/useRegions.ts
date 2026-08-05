import { useQuery } from '@tanstack/react-query';
import regionApi from '../api/regionApi';
import { DateRangeParams, PaginationParams, RegionDailyQueryParams } from '../types/common';

export function useRegionsDaily(params?: RegionDailyQueryParams) {
  return useQuery({
    queryKey: ['regionsDaily', params],
    queryFn: () => regionApi.getRegionsDaily(params),
    enabled: Boolean(params?.summary_date),
    staleTime: 60000,
  });
}

export function useRegionDaily(regionId: string, params?: DateRangeParams) {
  return useQuery({
    queryKey: ['regionDaily', regionId, params],
    queryFn: () => regionApi.getRegionDaily(regionId, params),
    enabled: Boolean(regionId),
    staleTime: 60000,
  });
}

export function useRegionStations(regionId: string, params?: DateRangeParams & PaginationParams & { summary_date?: string }) {
  return useQuery({
    queryKey: ['regionStations', regionId, params],
    queryFn: () => regionApi.getRegionStations(regionId, params),
    enabled: Boolean(regionId && params?.summary_date),
    staleTime: 60000,
  });
}
