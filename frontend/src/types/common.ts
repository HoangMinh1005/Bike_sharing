export interface ApiDataResponse<T> {
  data: T;
}

export interface PaginationMeta {
  count?: number;
  limit?: number;
  offset?: number;
}

export interface ApiListResponse<T> {
  data: T[];
  meta?: PaginationMeta;
}

export interface DateRangeParams {
  start_date?: string;
  end_date?: string;
}

export interface DateTimeRangeParams {
  start_time?: string;
  end_time?: string;
}

export interface PaginationParams {
  limit?: number;
  offset?: number;
}

export interface StationDailyQueryParams extends DateRangeParams, PaginationParams {
  summary_date?: string;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

export interface RegionDailyQueryParams extends DateRangeParams, PaginationParams {
  summary_date?: string;
}

export interface RankingQueryParams {
  ranking_date?: string;
  top_n?: number;
  demand_category?: 'ALL' | 'HIGH' | 'MEDIUM' | 'LOW';
}
