import { useQuery } from '@tanstack/react-query';
import { freshnessApi } from '../api/freshnessApi';

export function useFreshnessSummary() {
  return useQuery({
    queryKey: ['freshnessSummary'],
    queryFn: () => freshnessApi.getFreshnessSummary(),
    staleTime: 15000,
    refetchInterval: 30000,
  });
}

export default useFreshnessSummary;
