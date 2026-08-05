import { useQuery } from '@tanstack/react-query';
import systemApi from '../api/systemApi';
import { DateRangeParams, PaginationParams } from '../types/common';

export function useSystemLatest() {
  return useQuery({
    queryKey: ['systemLatest'],
    queryFn: () => systemApi.getSystemLatest(),
    staleTime: 60000,
  });
}

export function useSystemDaily(params?: DateRangeParams) {
  return useQuery({
    queryKey: ['systemDaily', params],
    queryFn: () => systemApi.getSystemDaily(params),
    staleTime: 60000,
  });
}

export function useSystemHourly(params?: DateRangeParams & PaginationParams) {
  return useQuery({
    queryKey: ['systemHourly', params],
    queryFn: () => systemApi.getSystemHourly(params),
    staleTime: 60000,
  });
}
