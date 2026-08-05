import axios from 'axios';

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export const apiClient = axios.create({
  baseURL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const errorMsg = error.response?.data?.error?.message || error.message || 'API request failed';
    console.error(`[API Error] ${error.config?.url}:`, errorMsg);
    return Promise.reject(new Error(errorMsg));
  }
);

export default apiClient;
