# GBFS Bike Sharing — SLA / SLO Monitoring Documentation

Tài liệu quy định và hướng dẫn vận hành **Hệ thống Giám sát SLA/SLO Giai đoạn 1** cho GBFS Bike Sharing Operation Intelligence.

---

## 1. Mục tiêu & Nguyên tắc Thiết kế

* **Lưu vết Lịch sử Metrics**: Chuyển đổi việc quan sát tính tươi của dữ liệu (Data Freshness) từ dạng kiểm tra tức thời sang **lưu trữ lịch sử theo thời gian** (Prometheus Time Series), làm cơ sở tính toán tỷ lệ phần trăm đạt SLA/SLO thực tế.
* **Tái sử dụng 100% Logic Hiện có**: Expose trực tiếp kết quả từ `api/services/freshness_service.py` (`get_data_freshness_summary()`) sang Prometheus Gauges mà **không viết lại query DB hay tạo trùng lặp business logic**.
* **Kiến trúc An toàn (Add-on Overlay)**: Triển khai dưới dạng file compose overlay riêng `docker-compose.monitoring.yml`, không can thiệp hay ảnh hưởng đến pipeline Airflow, FastAPI endpoints hay Nginx HTTPS hiện tại.

---

## 2. Chỉ số SLA/SLO Targets & Ngưỡng Đánh giá

### A. API Performance & Reliability SLA
| Chỉ số SLA | Mục tiêu (SLO) | Metrics trong Prometheus | Ngưỡng Warning / Critical |
| :--- | :--- | :--- | :--- |
| **API Error Rate** | **< 1.0%** 5xx errors | `http_requests_total{status_code=~"5.."}` | Critical nếu > 1% trong 5 phút |
| **Health API Latency (p95)** | **< 500 ms** | `http_request_duration_seconds_bucket` | Warning nếu > 500ms |
| **Dashboard API Latency (p95)** | **< 2.0 giây** | `http_request_duration_seconds_bucket` | Warning nếu > 2s |
| **Table & Search API Latency (p95)** | **< 3.0 giây** | `http_request_duration_seconds_bucket` | Warning nếu > 3s |

### B. Data Processing Freshness SLA
| Thành phần Data Pipeline | Mục tiêu Độ trễ (SLA) | Metrics trong Prometheus | Trạng thái Đánh giá |
| :--- | :--- | :--- | :--- |
| **Station Status Real-Time** | **$\le$ 30 phút** | `gbfs_station_status_freshness_lag_minutes` | **HEALTHY**: $\le 30$m<br>**WARNING**: $30 - 60$m<br>**STALE**: $> 60$m |
| **Hourly Mobility Data Mart** | **$\le$ 2 giờ (120 phút)** | `gbfs_hourly_mart_freshness_lag_minutes` | **HEALTHY**: $\le 120$m<br>**WARNING**: $120 - 240$m<br>**STALE**: $> 240$m |
| **Daily System Summary** | **Nút 1 (Daily)** | `gbfs_daily_summary_current` | **CURRENT (1)**: Đã tổng hợp ngày gần nhất<br>**MISSING/STALE (0)**: Bị chậm ngày |
| **Airflow DAG Execution Lag** | Theo Schedule | `gbfs_dag_latest_success_lag_minutes{dag_id="..."}` | Theo dõi độ trễ từng DAG |

### C. Infrastructure SLA
| Thành phần | Mục tiêu SLA | Exporter / Metric | Alert Trigger |
| :--- | :--- | :--- | :--- |
| **PostgreSQL Database** | **100% Uptime** | `postgres-exporter` (`up{job="postgres"}`) | Alert Critical ngay khi Down |
| **Redis Cache** | **100% Uptime** | `redis-exporter` (`up{job="redis"}`) | Alert Warning khi Down |
| **Host Disk Usage** | **< 80%** | `node-exporter` (`node_filesystem_free_bytes`) | Alert Warning khi $> 80\%$ |

---

## 3. Kiến trúc Giám sát: Internal Metrics vs External Uptime

```
+-------------------------------------------------------------------------+
|                              External World                             |
|                                                                         |
|  [ UptimeRobot ] ---> HTTPS Check (5m) ---> https://bike-sharing.duckdns.org
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                         Azure VM / Docker Network                       |
|                                                                         |
|  +--------------------+        +--------------------+                   |
|  |  FastAPI (/metrics)| <----  | Prometheus (9090)  |                   |
|  +--------------------+        +--------------------+                   |
|            |                              |                             |
|            v                              v                             |
|  +--------------------+        +--------------------+                   |
|  | Postgres / Redis   |        |   Grafana (3001)   | (SLA Dashboard)   |
|  +--------------------+        +--------------------+                   |
+-------------------------------------------------------------------------+
```

* **Prometheus + Grafana (Internal Metrics)**: Giám sát sâu bên trong Docker network, đo latency p95/p99, error rate %, độ trễ Data Freshness từng phút và tài nguyên VM.
* **UptimeRobot (External Monitoring)**: Giám sát từ bên ngoài môi trường Azure VM. Đảm bảo domain HTTPS và public endpoints luôn truy cập được ngay cả khi toàn bộ VM hoặc Nginx gặp sự cố.

---

## 4. Hướng dẫn Vận hành & Truy cập Giám sát

### A. Khởi chạy Monitoring Stack Overlay
Để bật stack monitoring cùng với hệ thống sản xuất:
```bash
docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.monitoring.yml \
  up -d --build
```

### B. Kết nối An toàn qua SSH Tunnel
Vì Prometheus (`9090`) và Grafana (`3001`) không mở công khai ra internet để bảo mật, hãy tạo SSH Tunnel từ máy cá nhân:
```bash
ssh -i ~/bike-sharing-key.pem -L 3001:localhost:3001 -L 9090:localhost:9090 azureuser@<VM-IP>
```

Sau khi mở SSH Tunnel:
* **Grafana Dashboard**: [http://localhost:3001](http://localhost:3001) *(User: admin / Pass: trong .env.prod)*
* **Prometheus Targets**: [http://localhost:9090/targets](http://localhost:9090/targets)

### C. Kiểm tra Endpoints Nội bộ
```bash
# Kiểm tra FastAPI Expose Prometheus Metrics
curl http://localhost:8000/metrics
```
