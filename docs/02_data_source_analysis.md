# Tài liệu Phân tích Nguồn Dữ liệu (Data Source Analysis)

Tài liệu này phân tích chi tiết các nguồn dữ liệu đầu vào của hệ thống **Bike Sharing Operation Intelligence**, bao gồm các feed GBFS (General Bikeshare Feed Specification), Weather API và Calendar CSV.

---

## 1. Các Nguồn Dữ liệu GBFS (General Bikeshare Feed Specification)

GBFS là tiêu chuẩn dữ liệu mở cho dịch vụ di chuyển công cộng chia sẻ. Dữ liệu được cung cấp dưới dạng các endpoint JSON cập nhật liên tục.

### 1.1. `system_information`
* **Vai trò**: Lưu trữ thông tin cấu hình và siêu dữ liệu (metadata) chung của toàn bộ hệ thống xe đạp.
* **Các trường quan trọng**:
  * `system_id`: Định danh duy nhất của hệ thống xe đạp.
  * `name`: Tên hệ thống (ví dụ: "Citi Bike").
  * `operator`: Nhà vận hành dịch vụ.
  * `timezone`: Múi giờ hoạt động của hệ thống (ví dụ: "Asia/Ho_Chi_Minh").
  * `url`: Địa chỉ trang chủ dịch vụ.
* **Đặc điểm & Lưu ý**:
  * **Múi giờ (Timezone)** là trường cực kỳ quan trọng để hệ thống căn chỉnh thời gian khi tính toán các chiều thời gian (date/hour) của Mart phân tích từ dữ liệu snapshot UTC của API.
  * Dữ liệu này hầu như không thay đổi. Tần suất thu thập: Thu thập hàng ngày (Daily) hoặc chạy duy nhất một lần khi khởi tạo hệ thống.

### 1.2. `system_regions`
* **Vai trò**: Định nghĩa ranh giới hành chính hoặc phân vùng địa lý vận hành của hệ thống xe đạp.
* **Các trường quan trọng**:
  * `region_id`: Định danh duy nhất của khu vực.
  * `name`: Tên khu vực (ví dụ: "Quận 1", "Quận 3").
* **Đặc điểm & Lưu ý**:
  * Dữ liệu này dùng để phân tích hiệu suất và mức độ mất cân bằng xe theo khu vực địa lý lớn hơn cấp trạm.
  * Cần join với bảng `station_information` thông qua khóa ngoại `region_id`.

### 1.3. `vehicle_types`
* **Vai trò**: Lưu trữ metadata về danh mục các loại phương tiện đang hoạt động trong hệ thống.
* **Các trường quan trọng**:
  * `vehicle_type_id`: Định danh duy nhất của loại xe.
  * `form_factor`: Kiểu dáng xe (ví dụ: `bike`, `scooter`).
  * `propulsion_type`: Hệ thống truyền động (ví dụ: `human` - xe đạp thường, `electric` - xe đạp điện).
  * `name`: Tên thương mại của loại xe.
  * `max_range_meters`: Quãng đường đi được tối đa đối với xe điện (e-bike) khi sạc đầy.
* **Đặc điểm & Lưu ý**:
  * Có giá trị phân tích sâu khi kết hợp với thông tin phân rã xe tại trạm (`station_status` có breakdown chi tiết số lượng xe khả dụng theo từng `vehicle_type_id`).

### 1.4. `station_information`
* **Vai trò**: Bảng kích thước (Dimension) chính lưu trữ thông tin cố định vật lý của các trạm xe đạp.
* **Các trường quan trọng**:
  * `station_id`: Định danh duy nhất của trạm xe.
  * `name`: Tên trạm xe đạp.
  * `lat`: Vĩ độ tọa độ địa lý.
  * `lon`: Kinh độ tọa độ địa lý.
  * `region_id`: Khóa ngoại liên kết với phân vùng địa lý.
  * `capacity`: Sức chứa tối đa của trạm (tổng số dock cắm xe).
  * `vehicle_capacity`: Sức chứa xe tối đa thực tế (nếu khác với capacity).
  * `rental_methods`: Phương thức thanh toán được chấp nhận tại trạm (`KEY`, `CREDITCARD`, `TRANSITCARD`, `PHONE`).
* **Đặc điểm & Lưu ý**:
  * Trường `capacity` được sử dụng làm tham chiếu cốt lõi cho các kiểm tra chất lượng dữ liệu (DQ Check), đảm bảo tổng số xe khả dụng và số dock trống tại một thời điểm không vượt quá dung lượng thiết kế của trạm.
  * Tọa độ `lat`/`lon` hiện tại được lưu trữ dưới dạng số thực float để phục vụ vẽ bản đồ, đồng thời sẵn sàng tích hợp với PostGIS cho các phân tích không gian nâng cao trong tương lai (ví dụ: tìm các trạm lân cận trong bán kính 500m để gợi ý người dùng di chuyển trả xe).

### 1.5. `station_status`
* **Vai trò**: Nguồn dữ liệu động (Fact) quan trọng nhất chứa trạng thái tức thời của các trạm xe đạp.
* **Các trường quan trọng**:
  * `station_id`: Định danh của trạm.
  * `num_vehicles_available`: Số lượng xe đang có sẵn tại trạm và có thể sử dụng được.
  * `num_docks_available`: Số lượng dock trống đang sẵn sàng để trả xe.
  * `vehicle_types_available`: Mảng JSON chứa chi tiết số lượng xe theo từng loại (`vehicle_type_id`) tại trạm.
  * `is_installed`: Trạm đã được lắp đặt hoàn thiện vật lý chưa (`true`/`false`).
  * `is_renting`: Trạm có đang cho phép thuê xe ra không (`true`/`false`).
  * `is_returning`: Trạm có đang cho phép trả xe vào không (`true`/`false`).
  * `last_reported`: Thời điểm trạm báo cáo trạng thái này về server trung tâm (dạng Unix timestamp).
* **Đặc điểm & Lưu ý**:
  * **Không có dữ liệu lịch sử**: Endpoint này chỉ hiển thị trạng thái hiện tại (real-time). Do đó, hệ thống bắt buộc phải chủ động kéo dữ liệu (collect) định kỳ 15 phút một lần để lưu trữ lại lịch sử biến động dữ liệu. Nếu pipeline bị gián đoạn, dữ liệu lịch sử của khoảng thời gian đó sẽ bị mất hoàn toàn.

---

## 2. Nguồn dữ liệu bổ trợ (Enrichment Data Sources)

### 2.1. Weather API (Dữ liệu thời tiết theo giờ)
* **Vai trò**: Cung cấp thông tin thời tiết phục vụ việc phân tích tương quan giữa các yếu tố môi trường ngoài trời và nhu cầu đi xe đạp của người dân.
* **Các trường quan trọng**:
  * `weather_time`: Thời điểm ghi nhận thời tiết (làm tròn theo giờ).
  * `temperature`: Nhiệt độ thực tế (°C).
  * `precipitation`: Lượng mưa ghi nhận (mm).
  * `wind_speed`: Tốc độ gió (km/h).
  * `humidity`: Độ ẩm không khí (%).
  * `weather_code`: Mã mô tả trạng thái thời tiết (nắng, mưa rào, sương mù...).

### 2.2. Calendar CSV (Dữ liệu lịch trình)
* **Vai trò**: Phân biệt tính chất các ngày trong năm để làm rõ hành vi thuê xe vào ngày làm việc thông thường so với các ngày nghỉ lễ/cuối tuần.
* **Các trường quan trọng**:
  * `date`: Ngày ghi nhận (YYYY-MM-DD).
  * `day_of_week`: Thứ trong tuần (Thứ Hai - Chủ Nhật).
  * `is_weekend`: Xác định có phải ngày cuối tuần (Thứ Bảy, Chủ Nhật) hay không (`true`/`false`).
  * `is_holiday`: Xác định có phải ngày nghỉ lễ chính thức theo luật lao động hay không (`true`/`false`).
