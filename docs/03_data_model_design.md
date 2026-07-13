# Thiết kế Mô hình Dữ liệu (Data Model Design)

Tài liệu này chi tiết hóa cấu trúc bảng, kiểu dữ liệu, các ràng buộc (constraints) và cơ chế tối ưu hóa truy vấn cho 3 phân lớp dữ liệu (Raw, Staging, Mart) trong Data Warehouse của hệ thống **Bike Sharing Operation Intelligence**.

---

## 1. Phân lớp Raw (Lưu trữ JSON thô)

Tầng Raw lưu trữ nguyên bản cấu trúc JSON phản hồi từ API. Toàn bộ các bảng trong tầng này nằm trong schema `raw`.

### 1.1. `raw.gbfs_feed_snapshots`
* **Mục đích**: Lưu snapshot của các API endpoints ít thay đổi (`system_information`, `system_regions`, `vehicle_types`, `station_information`).
* **Cấu trúc**:
  * `id` (SERIAL, PRIMARY KEY)
  * `batch_id` (UUID, NOT NULL): Định danh duy nhất cho mỗi phiên chạy của DAG.
  * `feed_name` (VARCHAR(50), NOT NULL): Tên feed tương ứng.
  * `fetched_at` (TIMESTAMP WITH TIME ZONE, NOT NULL): Thời điểm kéo dữ liệu.
  * `source_last_updated` (TIMESTAMP WITH TIME ZONE): Thời điểm dữ liệu được cập nhật ở nguồn gốc.
  * `ttl` (INTEGER): Thời gian sống của dữ liệu theo khai báo của API.
  * `raw_payload` (JSONB, NOT NULL): Toàn bộ payload JSON gốc.
  * `payload_hash` (VARCHAR(64), NOT NULL): Mã MD5/SHA256 của payload để kiểm tra trùng lặp nhanh.

### 1.2. `raw.station_status_snapshots`
* **Mục đích**: Lưu trữ snapshot trạng thái động của các trạm xe đạp theo chu kỳ thu thập.
* **Cấu trúc**:
  * `id` (BIGSERIAL, PRIMARY KEY)
  * `batch_id` (UUID, NOT NULL)
  * `station_id` (VARCHAR(50), NOT NULL)
  * `fetched_at` (TIMESTAMP WITH TIME ZONE, NOT NULL)
  * `snapshot_time` (TIMESTAMP WITH TIME ZONE, NOT NULL): Thời điểm chụp trạng thái (làm tròn hoặc lấy theo thời gian của hệ thống).
  * `source_last_updated` (TIMESTAMP WITH TIME ZONE)
  * `last_reported` (TIMESTAMP WITH TIME ZONE)
  * `raw_payload` (JSONB, NOT NULL)
  * `payload_hash` (VARCHAR(64), NOT NULL)
* **Khóa duy nhất (Unique Constraint)**:
  * `station_id` + `snapshot_time`

### 1.3. `raw.weather_hourly`
* **Mục đích**: Lưu dữ liệu thời tiết thô nhận về từ Weather API.
* **Cấu trúc**:
  * `id` (SERIAL, PRIMARY KEY)
  * `batch_id` (UUID, NOT NULL)
  * `location_name` (VARCHAR(100), NOT NULL)
  * `fetched_at` (TIMESTAMP WITH TIME ZONE, NOT NULL)
  * `weather_time` (TIMESTAMP WITH TIME ZONE, NOT NULL)
  * `raw_payload` (JSONB, NOT NULL)
  * `payload_hash` (VARCHAR(64), NOT NULL)

---

## 2. Phân lớp Staging (Chuẩn hóa cấu trúc)

Tầng Staging trích xuất các thuộc tính từ tài liệu JSON trong tầng Raw thành các cột có kiểu dữ liệu chuẩn, sẵn sàng để phân tích. Toàn bộ các bảng nằm trong schema `staging`.

### 2.1. `staging.system_information`
* `system_id` (VARCHAR(50), PRIMARY KEY)
* `system_name` (VARCHAR(100), NOT NULL)
* `operator` (VARCHAR(100))
* `timezone` (VARCHAR(50), NOT NULL)
* `url` (VARCHAR(255))
* `loaded_at` (TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP)

### 2.2. `staging.regions`
* `region_id` (VARCHAR(50), PRIMARY KEY)
* `region_name` (VARCHAR(100), NOT NULL)
* `loaded_at` (TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP)

### 2.3. `staging.vehicle_types`
* `vehicle_type_id` (VARCHAR(50), PRIMARY KEY)
* `vehicle_type_name` (VARCHAR(100))
* `form_factor` (VARCHAR(50), NOT NULL)
* `propulsion_type` (VARCHAR(50), NOT NULL)
* `max_range_meters` (INTEGER)
* `loaded_at` (TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP)

### 2.4. `staging.stations`
* `station_id` (VARCHAR(50), PRIMARY KEY)
* `station_name` (VARCHAR(255), NOT NULL)
* `short_name` (VARCHAR(50))
* `latitude` (DOUBLE PRECISION, NOT NULL)
* `longitude` (DOUBLE PRECISION, NOT NULL)
* `region_id` (VARCHAR(50) REFERENCES staging.regions(region_id))
* `capacity` (INTEGER, NOT NULL)
* `is_active` (BOOLEAN, DEFAULT TRUE)
* `loaded_at` (TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP)

### 2.5. `staging.station_status`
* `station_id` (VARCHAR(50) REFERENCES staging.stations(station_id))
* `snapshot_time` (TIMESTAMP WITH TIME ZONE, NOT NULL)
* `num_vehicles_available` (INTEGER, NOT NULL)
* `num_docks_available` (INTEGER, NOT NULL)
* `is_installed` (BOOLEAN, NOT NULL)
* `is_renting` (BOOLEAN, NOT NULL)
* `is_returning` (BOOLEAN, NOT NULL)
* `last_reported` (TIMESTAMP WITH TIME ZONE)
* `batch_id` (UUID, NOT NULL)
* `loaded_at` (TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP)
* **Khóa duy nhất (Composite Primary Key)**:
  * `station_id` + `snapshot_time`

### 2.6. `staging.station_vehicle_type_status`
* **Mục đích**: Phân tách số lượng xe khả dụng theo từng loại xe tại mỗi trạm dựa trên mảng JSON.
* **Cấu trúc**:
  * `station_id` (VARCHAR(50) REFERENCES staging.stations(station_id))
  * `snapshot_time` (TIMESTAMP WITH TIME ZONE, NOT NULL)
  * `vehicle_type_id` (VARCHAR(50) REFERENCES staging.vehicle_types(vehicle_type_id))
  * `count_available` (INTEGER, NOT NULL)
  * `batch_id` (UUID, NOT NULL)
  * `loaded_at` (TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP)
* **Khóa duy nhất (Composite Primary Key)**:
  * `station_id` + `snapshot_time` + `vehicle_type_id`

### 2.7. `staging.weather_hourly`
* `weather_time` (TIMESTAMP WITH TIME ZONE, PRIMARY KEY)
* `temperature` (NUMERIC(4, 2), NOT NULL)
* `precipitation` (NUMERIC(5, 2), DEFAULT 0)
* `wind_speed` (NUMERIC(5, 2))
* `humidity` (INTEGER)
* `weather_code` (VARCHAR(20))
* `loaded_at` (TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP)

### 2.8. `staging.calendar`
* `date` (DATE, PRIMARY KEY)
* `day_of_week` (INTEGER, NOT NULL): Thứ từ 1 (Chủ Nhật) đến 7 (Thứ Bảy).
* `is_weekend` (BOOLEAN, NOT NULL)
* `is_holiday` (BOOLEAN, DEFAULT FALSE)
* `loaded_at` (TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP)

---

## 3. Phân lớp Mart (Phục vụ truy vấn & API)

Tầng Mart chứa dữ liệu đã được làm sạch, kết hợp và tổng hợp theo các chiều thời gian, phân vùng để tối ưu hóa hiệu năng truy vấn cho các ứng dụng downstream. Toàn bộ các bảng nằm trong schema `mart`.

### 3.1. `mart.hourly_station_availability`
* **Mục đích**: Tổng hợp hiệu suất khả dụng của trạm theo từng giờ.
* **Cấu trúc**:
  * `station_id` (VARCHAR(50))
  * `station_name` (VARCHAR(255))
  * `region_id` (VARCHAR(50))
  * `region_name` (VARCHAR(100))
  * `date` (DATE)
  * `hour` (INTEGER)
  * `avg_vehicles_available` (NUMERIC(6, 2))
  * `avg_docks_available` (NUMERIC(6, 2))
  * `min_vehicles_available` (INTEGER)
  * `max_vehicles_available` (INTEGER)
  * `empty_rate` (NUMERIC(4, 3))
  * `full_rate` (NUMERIC(4, 3))
  * `unavailable_rate` (NUMERIC(4, 3))
  * `availability_level` (VARCHAR(30))
  * `updated_at` (TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP)
* **Khóa duy nhất**: `station_id` + `date` + `hour`

### 3.2. `mart.daily_station_summary`
* **Mục đích**: Báo cáo tổng hợp hiệu suất trạm theo ngày.
* **Cấu trúc**:
  * `station_id` (VARCHAR(50))
  * `station_name` (VARCHAR(255))
  * `region_id` (VARCHAR(50))
  * `region_name` (VARCHAR(100))
  * `date` (DATE)
  * `avg_vehicles_available` (NUMERIC(6, 2))
  * `avg_docks_available` (NUMERIC(6, 2))
  * `empty_hours` (NUMERIC(4, 2)): Số giờ trong ngày trạm bị hết xe.
  * `full_hours` (NUMERIC(4, 2)): Số giờ trong ngày trạm bị đầy dock.
  * `unavailable_hours` (NUMERIC(4, 2)): Số giờ trạm đóng cửa.
  * `avg_empty_rate` (NUMERIC(4, 3))
  * `avg_full_rate` (NUMERIC(4, 3))
  * `daily_demand_score` (NUMERIC(5, 2))
  * `updated_at` (TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP)
* **Khóa duy nhất**: `station_id` + `date`

### 3.3. `mart.station_demand_ranking`
* **Mục đích**: Xếp hạng nhu cầu cần tái điều phối xe giữa các trạm theo giờ.
* **Khóa duy nhất**: `date` + `hour` + `station_id`
* **Cấu trúc**:
  * `date` (DATE), `hour` (INTEGER)
  * `station_id` (VARCHAR(50)), `station_name` (VARCHAR(255)), `region_name` (VARCHAR(100))
  * `empty_rate` (NUMERIC(4, 3)), `full_rate` (NUMERIC(4, 3)), `unavailable_rate` (NUMERIC(4, 3))
  * `activity_change_score` (NUMERIC(4, 2))
  * `demand_score` (NUMERIC(5, 2))
  * `rank` (INTEGER): Thứ hạng ưu tiên (Rank càng nhỏ càng cần được xử lý sớm).

### 3.4. `mart.hourly_region_availability`
* **Mục đích**: Tổng hợp hiệu suất khả dụng theo phân vùng địa lý lớn theo giờ.
* **Khóa duy nhất**: `region_id` + `date` + `hour`
* **Cấu trúc**:
  * `region_id` (VARCHAR(50)), `region_name` (VARCHAR(100))
  * `date` (DATE), `hour` (INTEGER)
  * `station_count` (INTEGER): Số lượng trạm thuộc phân vùng này.
  * `avg_vehicles_available` (NUMERIC(8, 2)), `avg_docks_available` (NUMERIC(8, 2))
  * `avg_empty_rate` (NUMERIC(4, 3)), `avg_full_rate` (NUMERIC(4, 3))
  * `high_empty_risk_station_count` (INTEGER): Số lượng trạm có nguy cơ hết xe.
  * `high_full_risk_station_count` (INTEGER): Số lượng trạm có nguy cơ đầy dock.
  * `out_of_service_station_count` (INTEGER): Số lượng trạm bị khóa.

### 3.5. `mart.vehicle_type_availability_summary`
* **Mục đích**: Phân tích sự cân đối giữa các loại phương tiện (xe điện vs xe thường).
* **Khóa duy nhất**: `vehicle_type_id` + `date` + `hour`
* **Cấu trúc**:
  * `date` (DATE), `hour` (INTEGER)
  * `vehicle_type_id` (VARCHAR(50)), `vehicle_type_name` (VARCHAR(100))
  * `form_factor` (VARCHAR(50)), `propulsion_type` (VARCHAR(50))
  * `total_available` (INTEGER): Tổng số xe loại này sẵn có trong hệ thống.
  * `avg_available_per_station` (NUMERIC(6, 2))
  * `vehicle_type_share` (NUMERIC(4, 3)): Tỷ lệ phần trăm trên tổng số xe của hệ thống.
  * `station_count` (INTEGER): Số trạm có sẵn loại xe này.

### 3.6. `mart.weather_mobility_summary`
* **Mục đích**: Thống kê tương quan giữa thời tiết và hành vi thuê/trả xe toàn hệ thống.
* **Khóa duy nhất**: `date` + `hour`

### 3.7. `mart.station_anomalies`
* **Mục đích**: Ghi nhận các bất thường của trạm xe đạp để thông báo cho đội ngũ kỹ thuật.
* **Cấu trúc**:
  * `anomaly_id` (UUID, PRIMARY KEY)
  * `station_id` (VARCHAR(50)), `station_name` (VARCHAR(255)), `region_name` (VARCHAR(100))
  * `anomaly_type` (VARCHAR(50)): `STALE_DATA` (dữ liệu đứng im quá lâu), `EMPTY_TOO_LONG` (hết xe liên tục quá 6 giờ), `FULL_TOO_LONG` (đầy dock liên tục quá 6 giờ), `RENTING_DISABLED`, `RETURNING_DISABLED`, `SUDDEN_DROP` (giảm đột ngột số xe bất thường), `SUDDEN_INCREASE`.
  * `severity` (VARCHAR(20)): `LOW`, `MEDIUM`, `HIGH`.
  * `detected_at` (TIMESTAMP WITH TIME ZONE)
  * `metric_value` (NUMERIC(8, 2)): Giá trị đo được khi phát hiện lỗi.
  * `message` (TEXT): Nội dung chi tiết lỗi.
  * `status` (VARCHAR(20)): `ACTIVE` (đang xảy ra), `RESOLVED` (đã bình thường).

### 3.8. `mart.station_alerts`
* **Mục đích**: Quản lý các cảnh báo vận hành cấp bách (cần xử lý ngay).
* **Cấu trúc**:
  * `alert_id` (UUID, PRIMARY KEY)
  * `station_id` (VARCHAR(50)), `station_name` (VARCHAR(255))
  * `alert_type` (VARCHAR(50)): `EMPTY_ALERT`, `FULL_ALERT`, `OUT_OF_SERVICE_ALERT`.
  * `severity` (VARCHAR(20)): `CRITICAL`, `WARNING`.
  * `message` (TEXT)
  * `created_at` (TIMESTAMP WITH TIME ZONE)
  * `resolved_at` (TIMESTAMP WITH TIME ZONE)
  * `status` (VARCHAR(20)): `ACTIVE`, `RESOLVED`.

### 3.9. `mart.rebalancing_recommendations`
* **Mục đích**: Lưu trữ các khuyến nghị tái cân bằng xe (chuyển xe từ trạm thừa sang trạm thiếu).
* **Cấu trúc**:
  * `recommendation_id` (UUID, PRIMARY KEY)
  * `date` (DATE), `hour` (INTEGER)
  * `source_station_id` (VARCHAR(50)): Trạm nguồn (trạm thừa xe/có nguy cơ đầy dock).
  * `source_station_name` (VARCHAR(255))
  * `target_station_id` (VARCHAR(50)): Trạm đích (trạm thiếu xe/có nguy cơ hết xe).
  * `target_station_name` (VARCHAR(255))
  * `recommended_bikes_to_move` (INTEGER): Số xe đề xuất di chuyển.
  * `priority` (VARCHAR(20)): `HIGH`, `MEDIUM`, `LOW`.
  * `reason` (TEXT): Lý do đề xuất (ví dụ: "Trạm nguồn đầy dock 90%, trạm đích hết xe liên tục 2 giờ qua").
  * `created_at` (TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP)

---

## 4. Ràng buộc & Tối ưu hóa Database

Để đảm bảo hiệu năng tối đa cho hệ thống chạy lâu dài, các cơ chế sau được áp dụng tại PostgreSQL:

1. **Partitioning (Phân mảnh bảng)**:
   * Áp dụng phân mảnh theo cột `date` (Range Partitioning) cho các bảng giao dịch dung lượng lớn như:
     * `staging.station_status`
     * `staging.station_vehicle_type_status`
     * `mart.hourly_station_availability`
   * Cơ chế này giúp tăng tốc các câu lệnh `DELETE` khi backfill hoặc dọn dẹp dữ liệu cũ (chỉ cần DROP partition thay vì chạy `DELETE WHERE` quét toàn bảng).

2. **Indexes (Chỉ mục)**:
   * Đảm bảo mọi khóa ngoại và khóa composite được lập chỉ mục đầy đủ.
   * Tạo các chỉ mục phức hợp (Composite Index) cho các cột truy vấn thường xuyên cùng nhau ở API (e.g. `(station_id, date, hour)`).
