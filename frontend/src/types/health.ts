export interface ApiHealthStatus {
  status: 'healthy' | 'unhealthy' | string;
  database: 'healthy' | 'unhealthy' | string;
  redis: 'healthy' | 'unhealthy' | string;
  checked_at: string;
}
