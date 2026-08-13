from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class StationDailySummary(BaseSchema):
    summary_date: date
    station_id: str
    station_name: Optional[str] = None
    region_id: Optional[str] = None
    region_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    capacity: Optional[int] = None
    active_hour_count: Optional[int] = None
    total_observation_count: Optional[int] = None
    avg_bikes_available: Optional[float] = None
    avg_docks_available: Optional[float] = None
    avg_availability_rate: Optional[float] = None
    avg_dock_utilization_rate: Optional[float] = None
    empty_hour_count: Optional[int] = None
    full_hour_count: Optional[int] = None
    low_availability_hour_count: Optional[int] = None
    high_demand_hour_count: Optional[int] = None
    avg_temperature: Optional[float] = None
    total_precipitation: Optional[float] = None
    avg_wind_speed: Optional[float] = None


class RegionDailySummary(BaseSchema):
    summary_date: date
    region_id: str
    region_name: Optional[str] = None
    station_count: Optional[int] = None
    active_station_count: Optional[int] = None
    total_observation_count: Optional[int] = None
    avg_bikes_available: Optional[float] = None
    avg_docks_available: Optional[float] = None
    total_bikes_available: Optional[float] = None
    total_docks_available: Optional[float] = None
    avg_availability_rate: Optional[float] = None
    avg_dock_utilization_rate: Optional[float] = None
    empty_station_count: Optional[int] = None
    full_station_count: Optional[int] = None
    low_availability_station_count: Optional[int] = None
    high_demand_station_count: Optional[int] = None
    avg_temperature: Optional[float] = None
    total_precipitation: Optional[float] = None
    avg_wind_speed: Optional[float] = None


class SystemDailySummary(BaseSchema):
    summary_date: date
    station_count: Optional[int] = None
    active_station_count: Optional[int] = None
    region_count: Optional[int] = None
    total_observation_count: Optional[int] = None
    avg_bikes_available: Optional[float] = None
    avg_docks_available: Optional[float] = None
    total_bikes_available: Optional[float] = None
    total_docks_available: Optional[float] = None
    avg_availability_rate: Optional[float] = None
    avg_dock_utilization_rate: Optional[float] = None
    empty_station_count: Optional[int] = None
    full_station_count: Optional[int] = None
    low_availability_station_count: Optional[int] = None
    high_demand_station_count: Optional[int] = None
    avg_temperature: Optional[float] = None
    total_precipitation: Optional[float] = None
    avg_wind_speed: Optional[float] = None
    is_weekend: Optional[bool] = None
    is_holiday: Optional[bool] = None
    holiday_name: Optional[str] = None


class StationHourlyAvailability(BaseSchema):
    hour_bucket: datetime
    station_id: str
    station_name: Optional[str] = None
    region_id: Optional[str] = None
    region_name: Optional[str] = None
    capacity: Optional[int] = None
    observation_count: Optional[int] = None
    avg_bikes_available: Optional[float] = None
    avg_docks_available: Optional[float] = None
    availability_rate: Optional[float] = None
    dock_utilization_rate: Optional[float] = None
    empty_observation_count: Optional[int] = None
    full_observation_count: Optional[int] = None
    temperature: Optional[float] = None
    precipitation: Optional[float] = None
    wind_speed: Optional[float] = None
    is_weekend: Optional[bool] = None
    is_holiday: Optional[bool] = None


class HourlyMobilitySummary(BaseSchema):
    hour_bucket: datetime
    station_count: Optional[int] = None
    active_station_count: Optional[int] = None
    total_bikes_available: Optional[float] = None
    total_docks_available: Optional[float] = None
    avg_availability_rate: Optional[float] = None
    avg_dock_utilization_rate: Optional[float] = None
    temperature: Optional[float] = None
    precipitation: Optional[float] = None
    wind_speed: Optional[float] = None
    is_weekend: Optional[bool] = None
    is_holiday: Optional[bool] = None


class StationDemandRanking(BaseSchema):
    ranking_date: date
    station_id: str
    station_name: Optional[str] = None
    region_id: Optional[str] = None
    region_name: Optional[str] = None
    capacity: Optional[int] = None
    active_hour_count: Optional[int] = None
    avg_bikes_available: Optional[float] = None
    avg_docks_available: Optional[float] = None
    avg_availability_rate: Optional[float] = None
    avg_dock_utilization_rate: Optional[float] = None
    empty_hour_count: Optional[int] = None
    full_hour_count: Optional[int] = None
    low_availability_hour_count: Optional[int] = None
    high_demand_hour_count: Optional[int] = None
    demand_score: Optional[float] = None
    demand_rank: Optional[int] = None
    demand_category: Optional[Literal["HIGH", "MEDIUM", "LOW"]] = None
    is_weekend: Optional[bool] = None
    is_holiday: Optional[bool] = None
    holiday_name: Optional[str] = None


class PipelineHealth(BaseSchema):
    health_run_id: str
    checked_at: datetime
    monitored_dag_id: str
    pipeline_type: str
    expected_schedule: Optional[str] = None
    freshness_threshold_minutes: int
    latest_run_id: Optional[str] = None
    latest_run_status: Optional[str] = None
    latest_started_at: Optional[datetime] = None
    latest_finished_at: Optional[datetime] = None
    latest_duration_seconds: Optional[float] = None
    latest_records_extracted: Optional[int] = None
    latest_records_loaded: Optional[int] = None
    latest_records_rejected: Optional[int] = None
    latest_success_run_id: Optional[str] = None
    latest_success_finished_at: Optional[datetime] = None
    watermark_source_name: Optional[str] = None
    watermark_value: Optional[str] = None
    watermark_updated_at: Optional[datetime] = None
    freshness_lag_minutes: Optional[float] = None
    dq_total_checks: int = 0
    dq_failed_checks: int = 0
    dq_warning_checks: int = 0
    dq_critical_failed_checks: int = 0
    rejected_record_count: int = 0
    health_status: Literal["HEALTHY", "WARNING", "FAILED", "STALE", "UNKNOWN"]
    health_message: Optional[str] = None


class ApiHealth(BaseSchema):
    status: str
    database: str
    redis: str
    checked_at: datetime


class StationMetadata(BaseSchema):
    station_id: str
    station_name: Optional[str] = None
    region_id: Optional[str] = None
    region_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    capacity: Optional[int] = None


class DagRunFreshness(BaseSchema):
    dag_id: str
    latest_success_at: Optional[datetime] = None
    lag_minutes: Optional[float] = None
    status: Literal["HEALTHY", "WARNING", "STALE", "UNKNOWN"] = "UNKNOWN"


class DataFreshnessSummary(BaseSchema):
    status: Literal["HEALTHY", "WARNING", "STALE", "UNKNOWN"]
    checked_at: datetime
    latest_station_status_snapshot_at: Optional[datetime] = None
    station_status_lag_minutes: Optional[float] = None
    latest_hourly_mart_at: Optional[datetime] = None
    hourly_mart_lag_minutes: Optional[float] = None
    latest_daily_summary_date: Optional[date] = None
    latest_pipeline_health_status: Optional[str] = None
    latest_successful_dag_runs: list[DagRunFreshness] = []
    warnings: list[str] = []