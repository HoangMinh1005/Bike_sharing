export interface RegionDailySummary {
  summary_date: string;
  region_id: string;
  region_name?: string;
  station_count?: number;
  active_station_count?: number;
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
}
