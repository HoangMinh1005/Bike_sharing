export type DemandCategory = 'HIGH' | 'MEDIUM' | 'LOW';

export interface StationDemandRanking {
  ranking_date: string;
  station_id: string;
  station_name?: string;
  region_id?: string;
  region_name?: string;
  capacity?: number;
  active_hour_count?: number;
  avg_bikes_available?: number;
  avg_docks_available?: number;
  avg_availability_rate?: number;
  avg_dock_utilization_rate?: number;
  empty_hour_count?: number;
  full_hour_count?: number;
  low_availability_hour_count?: number;
  high_demand_hour_count?: number;
  demand_score?: number;
  demand_rank?: number;
  demand_category?: DemandCategory;
  is_weekend?: boolean;
  is_holiday?: boolean;
  holiday_name?: string;
}
