export interface SystemDailySummary {
  summary_date: string;
  station_count?: number;
  active_station_count?: number;
  region_count?: number;
  total_observation_count?: number;
  avg_bikes_available?: number;
  avg_docks_available?: number;
  total_bikes_available?: number;
  total_docks_available?: number;
  avg_availability_rate?: number;
  avg_dock_utilization_rate?: number;
  empty_station_count?: number;
  full_station_count?: number;
  low_availability_station_count?: number;
  high_demand_station_count?: number;
  avg_temperature?: number;
  total_precipitation?: number;
  avg_wind_speed?: number;
  is_weekend?: boolean;
  is_holiday?: boolean;
  holiday_name?: string;
}

export interface HourlyMobilitySummary {
  hour_bucket: string;
  station_count?: number;
  active_station_count?: number;
  total_bikes_available?: number;
  total_docks_available?: number;
  avg_availability_rate?: number;
  avg_dock_utilization_rate?: number;
  temperature?: number;
  precipitation?: number;
  wind_speed?: number;
  is_weekend?: boolean;
  is_holiday?: boolean;
}
