import apiClient from './client';
import { ApiDataResponse } from '../types/common';
import { DataFreshnessSummary } from '../types/freshness';

export const freshnessApi = {
  getFreshnessSummary: async (): Promise<ApiDataResponse<DataFreshnessSummary>> => {
    const response = await apiClient.get<ApiDataResponse<DataFreshnessSummary>>('/freshness/summary');
    return response.data;
  },
};

export default freshnessApi;
