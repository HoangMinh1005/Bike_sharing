# UptimeRobot External Monitoring Setup Guide

Hướng dẫn cấu hình **UptimeRobot External Monitoring** cho hệ thống GBFS Bike Sharing Operation Intelligence (`https://bike-sharing.duckdns.org`).

---

## 1. Vai trò của UptimeRobot trong Hệ thống Giám sát

* **Prometheus & Grafana**: Thu thập metrics **nội bộ (Internal Metrics)** bên trong Docker network của Azure VM (đo CPU, RAM, Latency, Data Freshness lag từng phút).
* **UptimeRobot**: Thu thập tính sẵn sàng **từ bên ngoài (External Availability)** qua mạng internet công cộng.
* **Tại sao cần cả hai?**: Nếu Azure VM bị mất mạng, sập nguồn hoặc Nginx bị lỗi SSL, Prometheus chạy cùng VM cũng sẽ ngưng hoạt động. Khi đó, UptimeRobot đóng vai trò là "người quan sát độc lập bên ngoài" để phát hiện sự cố ngay lập tức và gửi thông báo.

---

## 2. Danh sách Monitor Cần Khởi tạo

Bạn có thể đăng ký tài khoản miễn phí tại [UptimeRobot.com](https://uptimerobot.com) và tạo 3–4 monitors sau:

### Monitor 1: GBFS Web Dashboard HTTPS
* **Monitor Type**: `HTTP(s)`
* **Friendly Name**: `GBFS Dashboard HTTPS`
* **URL (or IP)**: `https://bike-sharing.duckdns.org/`
* **Monitoring Interval**: `5 minutes` (Free plan default)
* **Expected HTTP Status**: `200 OK`

### Monitor 2: GBFS FastAPI Health Endpoint
* **Monitor Type**: `HTTP(s)`
* **Friendly Name**: `GBFS FastAPI Health API`
* **URL (or IP)**: `https://bike-sharing.duckdns.org/api/v1/health`
* **Monitoring Interval**: `5 minutes`
* **Expected HTTP Status**: `200 OK`
* **Keyword Monitoring (Optional)**: Chọn `Keyword Exists` với từ khóa `healthy` hoặc `OK`.

### Monitor 3: GBFS Interactive API Documentation
* **Monitor Type**: `HTTP(s)`
* **Friendly Name**: `GBFS API Docs`
* **URL (or IP)**: `https://bike-sharing.duckdns.org/docs`
* **Monitoring Interval**: `5 minutes`
* **Expected HTTP Status**: `200 OK`

### Monitor 4 (Optional): SSL Certificate Expiration
* **Monitor Type**: `Port` hoặc `SSL Certificate` (nếu tài khoản hỗ trợ)
* **Friendly Name**: `GBFS DuckDNS SSL Certificate`
* **URL / Host**: `bike-sharing.duckdns.org`
* **Port**: `443`
* **Cảnh báo**: Báo động khi Let's Encrypt SSL certificate còn dưới 14 ngày hết hạn.

---

## 3. Cấu hình Cảnh báo Notification Channels (Alert Contacts)

Trong giao diện UptimeRobot:
1. Vào **My Settings** $\rightarrow$ **Alert Contacts**.
2. Thêm phương thức nhận tin nhắn khi có sự cố Down/Up:
   * **Email**: Địa chỉ email quản trị hệ thống.
   * **Telegram / Discord / Webhook**: Kết nối Telegram Bot channel để nhận cảnh báo tức thì khi domain bị văng hoặc HTTPS 502/504 Bad Gateway.

---

## 4. Kiểm tra & Kiểm chứng Uptime Status

* Sau khi khởi tạo thành công, giao diện UptimeRobot sẽ hiển thị thanh trạng thái xanh **100.00% Uptime**.
* UptimeRobot tự động tính toán chỉ số **Availability SLA (Ví dụ: 99.9% Uptime/tháng)** để đưa vào báo cáo SLO cho mentor / ban quản trị.
