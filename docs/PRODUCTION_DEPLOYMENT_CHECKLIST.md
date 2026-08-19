# Production Deployment & Verification Checklist

Bảng kiểm tra (Checklist) chuẩn hóa dành cho kỹ sư trước, trong và sau khi triển khai hệ thống **GBFS Bike Sharing Operation Intelligence** lên máy chủ production (Azure VM).

---

## 1. Danh mục Kiểm tra Trước Triển khai (Pre-Flight Checks)

- [ ] **File `.env.prod` đã sẵn sàng**:
  - [ ] Mật khẩu `POSTGRES_PASSWORD` và `AIRFLOW_PASSWORD` là chuỗi bảo mật ngẫu nhiên.
  - [ ] `DATABASE_URL` sử dụng container name `postgres` (không dùng `localhost`).
  - [ ] `REDIS_URL` sử dụng container name `redis` (không dùng `localhost`).
  - [ ] `ALERT_WEBHOOK_ENABLED` đã được cấu hình kèm `TELEGRAM_BOT_TOKEN` và `TELEGRAM_CHAT_ID`.
  - [ ] `VITE_API_BASE_URL` được đặt đúng mode:
    - Mode A (Direct port): `http://<public-ip>:8000/api/v1`
    - Mode B/C (Nginx / HTTPS): `/api/v1`
- [ ] **Tường lửa Azure NSG đã được thiết lập**:
  - [ ] Port `22` (SSH) chỉ mở cho `My IP`.
  - [ ] Port `80` (HTTP) và `443` (HTTPS) mở cho Internet.
  - [ ] Port `5432` (PostgreSQL) và `6379` (Redis) **ĐÃ ĐÓNG HOÀN TOÀN** khỏi Public Internet.

---

## 2. Kiểm tra Cú pháp Cấu hình Docker Compose

Chạy lệnh xác thực cú pháp trước khi khởi động:

```bash
# Kiểm tra cấu hình compose cơ sở
docker compose -f docker-compose.prod.yml --env-file .env.prod config

# Kiểm tra cấu hình compose tích hợp Nginx
docker compose -f docker-compose.prod.yml -f docker-compose.nginx.yml --env-file .env.prod config
```
*Kết quả:* Không có lỗi cú pháp YAML hoặc biến môi trường thiếu.

---

## 3. Khởi động và Xác nhận Trạng thái Containers

```bash
# Khởi động dịch vụ
docker compose -f docker-compose.prod.yml -f docker-compose.nginx.yml --env-file .env.prod up -d

# Kiểm tra trạng thái toàn bộ containers
docker compose -f docker-compose.prod.yml -f docker-compose.nginx.yml ps
```

### ✅ Tiêu chí đạt (Acceptance Criteria):
* `bike_postgres`: Trạng thái **`Up (healthy)`**
* `bike_redis`: Trạng thái **`Up (healthy)`**
* `bike_fastapi`: Trạng thái **`Up (healthy)`**
* `bike_frontend`: Trạng thái **`Up`**
* `bike_airflow_webserver`: Trạng thái **`Up (healthy)`**
* `bike_airflow_scheduler`: Trạng thái **`Up`**
* `bike_nginx`: Trạng thái **`Up`**

---

## 4. Ma trận Kiểm thử Endpoint (Health & Routing Matrix)

Thực hiện các lệnh `curl` kiểm tra phản hồi từ máy chủ VM:

| Endpoint | Lệnh kiểm tra | Mã phản hồi mong đợi | Kết quả kiểm tra |
| :--- | :--- | :---: | :--- |
| **Frontend SPA** | `curl -I http://localhost/` | `200 OK` | `[ ] Pass` |
| **FastAPI Health** | `curl -s http://localhost/api/v1/health` | `{"status":"healthy",...}` | `[ ] Pass` |
| **Swagger Docs** | `curl -I http://localhost/docs` | `200 OK` | `[ ] Pass` |
| **OpenAPI Schema** | `curl -s http://localhost/openapi.json` | `{"openapi":"3.1.0",...}` | `[ ] Pass` |
| **Alerts Stats** | `curl -s http://localhost/api/v1/alerts/stats` | `{"data":{"total_active":...}}` | `[ ] Pass` |
| **Airflow UI** | `curl -I http://localhost/airflow/` | `200 OK` hoặc `302 Found` | `[ ] Pass` |

---

## 5. Kiểm thử Giao diện Người dùng (Frontend UI Checks)

Truy cập Dashboard qua trình duyệt: `http(s)://<domain-or-ip>/`

- [ ] **Overview Dashboard**: Tải đầy đủ các thẻ chỉ số (Active Stations, Availability Rate, Dock Utilization, Total Bikes/Docks).
- [ ] **Biểu đồ xu hướng**: Line chart và Bar chart hiển thị dữ liệu lịch sử đầy đủ theo thứ tự thời gian.
- [ ] **API Status Badge**: Huy hiệu góc màn hình hiển thị màu xanh lá: **`API Online`**.
- [ ] **Active Alerts Panel**: Trên trang Pipeline Health, khối Alert hiển thị thu gọn mặc định và xổ xuống mượt mà khi bấm.
- [ ] **Station Detail & Region Detail**: Bấm vào chi tiết từng trạm hiển thị đúng chỉ số của ngày mới nhất.

---

## 6. Kiểm tra An toàn & Bảo mật (Security Audits)

Kiểm tra từ máy tính cá nhân bên ngoài (không dùng SSH):

```bash
# 1. Kiểm tra Port 5432 (Postgres) - Phải bị từ chối kết nối
nc -zv -w 3 <public-ip> 5432
# Kỳ vọng: Connection timed out / Connection refused

# 2. Kiểm tra Port 6379 (Redis) - Phải bị từ chối kết nối
nc -zv -w 3 <public-ip> 6379
# Kỳ vọng: Connection timed out / Connection refused
```

---

## 7. Kế hoạch Hoàn tác Nhanh (Rollback Procedure)

Nếu gặp bất kỳ sự cố nào với lớp Nginx hoặc chứng chỉ SSL, bạn có thể hoàn tác ngay lập tức về chế độ Direct Port chỉ với 1 thao tác:

```bash
# 1. Dừng lớp Nginx
docker compose -f docker-compose.nginx.yml down

# 2. Khởi động lại chế độ Direct Port gốc
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
```
*Hệ thống sẽ ngay lập tức hoạt động lại qua các cổng trực tiếp `3000`, `8000`, `8080` như cũ!*
