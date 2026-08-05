export interface StationDailySummary {
  summary_date: string;
  station_id: string;
  station_name?: string;
  region_id?: string;
  region_name?: string;
  latitude?: number;
  longitude?: number;
  capacity?: number;
  active_hour_count?: number;
  total_observation_count?: number;
  avg_bikes_available?: number;
  avg_docks_available?: number;
  avg_availability_rate?: number;
  avg_dock_utilization_rate?: number;
  empty_hour_count?: number;
  full_hour_count?: number;
  low_availability_hour_count?: number;
  high_demand_hour_count?: number;
  avg_temperature?: number;
  total_precipitation?: number;
  avg_wind_speed?: number;
}

export interface StationHourlyAvailability {
  hour_bucket: string;
  station_id: string;
  station_name?: string;
  region_id?: string;
  region_name?: string;
  capacity?: number;
  observation_count?: number;
  avg_bikes_available?: number;
  avg_docks_available?: number;
  availability_rate?: number;
  dock_utilization_rate?: number;
  empty_observation_count?: number;
  full_observation_count?: number;
  temperature?: number;
  precipitation?: number;
  wind_speed?: number;
  is_weekend?: boolean;
  is_holiday?: boolean;
}

export interface StationMetadata {
  station_id: string;
  station_name?: string;
  region_id?: string;
  region_name?: string;
  latitude?: number;
  longitude?: number;
  capacity?: number;
}
