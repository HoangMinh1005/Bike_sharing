# Tài liệu Yêu cầu Nghiệp vụ (Business Requirements)

Tài liệu này mô tả chi tiết các yêu cầu nghiệp vụ, mục tiêu vận hành, đối tượng sử dụng dữ liệu và định nghĩa các chỉ số hiệu năng (metrics) cốt lõi của hệ thống **Bike Sharing Operation Intelligence**.

---

## 1. Tổng quan Dự án

Hệ thống được xây dựng nhằm thu thập, xử lý và phân tích dữ liệu từ các trạm xe đạp công cộng thời gian thực (GBFS Feeds). Dữ liệu này sau đó được tích hợp với dữ liệu thời tiết và lịch trình để cung cấp các phân tích thông minh, giúp nâng cao hiệu quả vận hành dịch vụ xe đạp công cộng.

Hệ thống giải quyết các bài toán thực tế:
* **Trạm nào thường xuyên hết xe** vào các khung giờ cao điểm?
* **Trạm nào thường bị đầy dock** khiến người dùng không thể trả xe?
* **Khu vực nào đang bị mất cân bằng** giữa cung (xe khả dụng) và cầu (dock trống)?
* **Có sự cố bất thường nào xảy ra** tại các trạm không (ví dụ: mất kết nối dữ liệu, hỏng hệ thống thuê/trả)?
* **Làm thế nào để điều phối xe** (rebalance) từ trạm thừa sang trạm thiếu một cách tối ưu nhất?

---

## 2. Đối tượng tiêu thụ dữ liệu (Downstream Consumers)

Hệ thống dữ liệu sau khi tổng hợp sẽ phục vụ cho 4 nhóm đối tượng chính thông qua cổng API của FastAPI:

### 2.1. Ban Vận hành (Operation Dashboard)
* **Giao diện hiển thị**:
  * Danh sách top các trạm có nguy cơ hết xe hoặc đầy dock cao nhất trong giờ tiếp theo.
  * Các khu vực địa lý có mật độ cảnh báo mất cân bằng cao.
  * Các cảnh báo (Alerts) đang kích hoạt thời gian thực.
  * Đề xuất điều phối xe (Rebalancing recommendations) chi tiết.

### 2.2. Người dùng cuối (Web/Mobile App)
* **Ứng dụng hiển thị**:
  * Số lượng xe khả dụng và số dock trống thực tế của từng trạm tại thời điểm hiện tại.
  * Trạng thái hoạt động của trạm (đang mở cửa, khóa thuê, khóa trả).
  * Dự báo mức độ khả dụng của trạm trong các giờ tiếp theo để người dùng chủ động lập lộ trình.

### 2.3. Hệ thống Điều phối tự động (Internal Operation Service)
* **Dịch vụ tự động**:
  * Tự động điều động đội ngũ xe tải chuyển xe dựa trên đề xuất điều phối từ Mart dữ liệu.
  * Danh sách các trạm bất thường cần nhân viên kỹ thuật đến kiểm tra hiện trường.

### 2.4. Đội ngũ Kỹ sư Dữ liệu (Data Engineering Monitoring)
* **Hệ thống giám sát**:
  * Theo dõi tính ổn định của pipeline thu thập dữ liệu (trạng thái chạy của DAGs, thời gian hoàn thành).
  * Giám sát chất lượng dữ liệu (Data Quality) và thống kê các bản ghi bị loại bỏ (rejected records) do lỗi DQ.
  * Đo lường độ trễ dữ liệu (data freshness) so với thời gian thực.

---

## 3. Định nghĩa các Chỉ số Vận hành (Metrics Definitions)

### 3.1. Các tỷ lệ trạng thái (Rates)
Các tỷ lệ này được tính toán trong một khoảng thời gian quan sát nhất định (mỗi giờ hoặc mỗi ngày):

* **Tỷ lệ hết xe (Empty Rate)**:
  $$\text{empty\_rate} = \frac{\text{Số lượng snapshot có } num\_vehicles\_available \le empty\_threshold}{\text{Tổng số lượng snapshot thu thập}}$$
  *(Mặc định $empty\_threshold = 2$)*

* **Tỷ lệ đầy dock (Full Rate)**:
  $$\text{full\_rate} = \frac{\text{Số lượng snapshot có } num\_docks\_available \le full\_threshold}{\text{Tổng số lượng snapshot thu thập}}$$
  *(Mặc định $full\_threshold = 2$)*

* **Tỷ lệ ngừng phục vụ (Unavailable Rate)**:
  $$\text{unavailable\_rate} = \frac{\text{Số lượng snapshot có } is\_renting = false \text{ hoặc } is\_returning = false}{\text{Tổng số lượng snapshot thu thập}}$$

### 3.2. Điểm nhu cầu điều phối (Demand Score)
Dùng để xếp hạng độ ưu tiên điều phối của các trạm xe đạp:
$$\text{demand\_score} = \text{empty\_rate} \times 0.45 + \text{full\_rate} \times 0.30 + \text{unavailable\_rate} \times 0.15 + \text{activity\_change\_score} \times 0.10$$

Trong đó, $\text{activity\_change\_score}$ được tính dựa trên độ biến động số lượng xe giữa các snapshot kế tiếp nhằm đo lường mức độ tương tác thực tế của khách hàng tại trạm đó:
$$\text{vehicle\_delta} = \text{previous\_num\_vehicles\_available} - \text{current\_num\_vehicles\_available}$$

---

## 4. Phân loại Cấp độ Khả dụng (Availability Level)

Mỗi trạm xe đạp tại một khung giờ sẽ được phân loại vào một trong các cấp độ sau để hiển thị trực quan trên bản đồ nhiệt (Heatmap):

* **`OUT_OF_SERVICE`**: Trạm bị khóa tính năng thuê (`is_renting = false`) hoặc trả xe (`is_returning = false`).
* **`HIGH_EMPTY_RISK`**: Trạm có nguy cơ hết xe rất cao (số lượng xe khả dụng trung bình $\le 2$ hoặc tỷ lệ hết xe trong giờ $\ge 70\%$).
* **`HIGH_FULL_RISK`**: Trạm có nguy cơ đầy dock rất cao (số dock trống trung bình $\le 2$ hoặc tỷ lệ đầy dock trong giờ $\ge 70\%$).
* **`LOW_AVAILABILITY`**: Trạm còn rất ít xe khả dụng (số lượng xe khả dụng trung bình $\le 5$).
* **`NORMAL`**: Trạm hoạt động ổn định, số lượng xe và dock trống cân bằng.
