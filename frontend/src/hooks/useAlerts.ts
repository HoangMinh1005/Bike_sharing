import { useQuery } from '@tanstack/react-query';
import { alertApi } from '../api/alertApi';

export const useAlertStats = () => {
  return useQuery({
    queryKey: ['alerts', 'stats'],
    queryFn: () => alertApi.getStats(),
    refetchInterval: 30000, // 30s
    staleTime: 15000,
  });
};

export const useLatestAlerts = (limit = 20) => {
  return useQuery({
    queryKey: ['alerts', 'latest', limit],
    queryFn: () => alertApi.getLatest(limit),
    refetchInterval: 30000,
    staleTime: 15000,
  });
};

export const useActiveAlerts = (limit = 50) => {
  return useQuery({
    queryKey: ['alerts', 'active', limit],
    queryFn: () => alertApi.getActive(limit),
    refetchInterval: 30000,
    staleTime: 15000,
  });
};
