import { AxiosError } from 'axios';

export interface ParsedError {
  title: string;
  message: string;
  severity: 'info' | 'warning' | 'error';
  technicalDetails?: string;
  isNetworkError: boolean;
  isServerError: boolean;
  isNotFound: boolean;
}

/**
 * Parse an API or network error into user-friendly title, message, and severity.
 */
export function parseApiError(error: unknown, fallbackEmptyMessage?: string): ParsedError {
  if (!error) {
    return {
      title: 'No data available yet',
      message: fallbackEmptyMessage || 'The pipeline is running, but this dataset has not accumulated enough records yet.',
      severity: 'info',
      isNetworkError: false,
      isServerError: false,
      isNotFound: true,
    };
  }

  const axiosError = error as AxiosError<{ error?: { code?: string; message?: string }; detail?: string | object }>;

  // Case A: Network / Connection Error (Backend unreachable / offline)
  if (!axiosError.response || axiosError.code === 'ERR_NETWORK' || axiosError.code === 'ECONNABORTED') {
    return {
      title: 'Backend API is unavailable',
      message: 'The dashboard could not connect to the FastAPI backend. Please check whether the API container is running.',
      severity: 'error',
      technicalDetails: axiosError.message || String(error),
      isNetworkError: true,
      isServerError: false,
      isNotFound: false,
    };
  }

  const statusCode = axiosError.response.status;

  // Case B: Backend 500 Internal Server Error
  if (statusCode >= 500) {
    const serverMessage =
      axiosError.response.data?.error?.message ||
      (typeof axiosError.response.data?.detail === 'string' ? axiosError.response.data.detail : undefined);

    return {
      title: 'Backend query failed',
      message: 'The API is reachable, but the backend could not query the required data. Please check FastAPI logs and database schema.',
      severity: 'error',
      technicalDetails: serverMessage ? `Server (HTTP ${statusCode}): ${serverMessage}` : `HTTP ${statusCode} Server Error`,
      isNetworkError: false,
      isServerError: true,
      isNotFound: false,
    };
  }

  // Case C: 404 Not Found (Data not yet generated / missing for date)
  if (statusCode === 404) {
    const notFoundMessage =
      axiosError.response.data?.error?.message ||
      (typeof axiosError.response.data?.detail === 'string' ? axiosError.response.data.detail : undefined);

    return {
      title: 'No data available yet',
      message: fallbackEmptyMessage || notFoundMessage || 'The pipeline is running, but this dataset has not accumulated enough records yet.',
      severity: 'info',
      technicalDetails: notFoundMessage ? `HTTP 404: ${notFoundMessage}` : undefined,
      isNetworkError: false,
      isServerError: false,
      isNotFound: true,
    };
  }

  // Default / Client Error (400, 422, etc.)
  const clientMessage =
    axiosError.response.data?.error?.message ||
    (typeof axiosError.response.data?.detail === 'string'
      ? axiosError.response.data.detail
      : typeof axiosError.response.data?.detail === 'object'
      ? JSON.stringify(axiosError.response.data.detail)
      : axiosError.message);

  return {
    title: 'Unable to load data',
    message: clientMessage || 'The request could not be completed with the provided parameters.',
    severity: 'warning',
    technicalDetails: `HTTP ${statusCode}: ${clientMessage}`,
    isNetworkError: false,
    isServerError: false,
    isNotFound: false,
  };
}

export default parseApiError;
