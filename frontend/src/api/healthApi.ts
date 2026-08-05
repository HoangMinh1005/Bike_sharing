import apiClient from './client';
import { ApiDataResponse } from '../types/common';
import { ApiHealthStatus } from '../types/health';

export const healthApi = {
  getHealth: async (): Promise<ApiDataResponse<ApiHealthStatus>> => {
    const res = await apiClient.get<ApiDataResponse<ApiHealthStatus>>('/health');
    return res.data;
  },
};

export default healthApi;
