import { useQuery } from '@tanstack/react-query';
import healthApi from '../api/healthApi';

export function useApiHealth() {
  return useQuery({
    queryKey: ['apiHealth'],
    queryFn: () => healthApi.getHealth(),
    staleTime: 30000,
    refetchInterval: 60000,
  });
}
