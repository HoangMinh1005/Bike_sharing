# Centralized Alerting & Telegram Notification System

Tài liệu hướng dẫn vận hành, cấu hình và quản trị hệ thống **Cảnh báo tập trung (Centralized Alerting)** và thông báo qua **Telegram Bot** cho nền tảng GBFS Bike Sharing Operation Intelligence.

---

## 1. Tổng quan kiến trúc (Architecture Overview)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               AIRFLOW ORCHESTRATION                                   │
│  - Task Failure (on_failure_callback)                                                  │
│  - Stale / Failed Monitored DAGs (pipeline_health_dag)                                 │
└─────────────────────────────────────────┬──────────────────────────────────────────────┘
                                          │
                                          ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               src/alerts/ MODULE                                       │
│  1. Dedup Filter (ALERT_DEDUP_WINDOW_MINUTES: Tránh spam khi retry)                    │
│  2. Record to PostgreSQL (etl_metadata.alert_events)                                   │
│  3. Dispatch via Telegram Bot API (Non-blocking: Pipeline không bao giờ fail nếu lỗi)  │
└──────────────────┬───────────────────────────────────────────────┬─────────────────────┘
                   │                                               │
                   ▼                                               ▼
┌────────────────────────────────────┐           ┌───────────────────────────────────────┐
│     POSTGRESQL METADATA TABLE      │           │         TELEGRAM BOT API              │
│    etl_metadata.alert_events       │           │  Direct HTTP POST (10s timeout)       │
└──────────────────┬─────────────────┘           └───────────────────────────────────────┘
                   │
                   ▼
┌────────────────────────────────────┐
│      FASTAPI READ-ONLY API         │
│   GET /api/v1/alerts/stats         │
│   GET /api/v1/alerts/active        │
│   GET /api/v1/alerts/latest        │
│   GET /api/v1/alerts/history       │
└──────────────────┬─────────────────┘
                   │
                   ▼
┌────────────────────────────────────┐
│   REACT DASHBOARD READ-ONLY PANEL  │
│   (Pipeline Health -> Alerts)      │
└────────────────────────────────────┘
```

### Nguyên tắc an toàn cốt lõi (Non-blocking Guarantee):
1. **Zero Impact on Pipeline**: Việc ghi alert và gửi Telegram chạy trong khối `try...except` độc lập. Nếu Telegram API gặp sự cố (timeout, mạng chập chờn, token sai), trạng thái trong DB sẽ ghi nhận `FAILED_TO_SEND` và **tuyệt đối không bao giờ làm fail Airflow Task / DAG**.
2. **Không có Queue phức tạp**: Sử dụng gọi HTTP trực tiếp qua thư viện `requests` có timeout (mặc định 10s), không cần thêm Celery, RabbitMQ hay Kafka.
3. **Bảo mật Secret**: Toàn bộ Token và Chat ID được truyền qua biến môi trường. Tuyệt đối không hardcode trong source code.
4. **Chống bão tin nhắn (Deduplication)**: Cùng một `alert_type`, `dag_id`, `task_id` xuất hiện trong vòng `ALERT_DEDUP_WINDOW_MINUTES` sẽ được gom lại (`SKIPPED`) để tránh làm ngập hộp thư Telegram.

---

## 2. Các biến môi trường cấu hình (Environment Variables)

Cấu hình trong file `.env.prod` trên máy chủ VM:

```bash
# ==============================================================================
# Centralized Alerting & Telegram Bot Notification Configuration
# ==============================================================================
ALERT_WEBHOOK_ENABLED=false           # Bật/tắt gửi thông báo qua Webhook (true/false)
ALERT_WEBHOOK_PROVIDER=telegram       # Provider chính (hiện tại: telegram)
TELEGRAM_BOT_TOKEN=                   # Bot Token lấy từ @BotFather
TELEGRAM_CHAT_ID=                     # Chat ID nhận tin nhắn (cá nhân hoặc group)
ALERT_DEDUP_WINDOW_MINUTES=60         # Khoảng thời gian chống gửi lặp alert (phút)
ALERT_REQUEST_TIMEOUT_SECONDS=10      # Timeout khi gọi Telegram API (giây)
```

---

## 3. Hướng dẫn tạo Telegram Bot và lấy Chat ID

### Bước 1: Tạo Bot qua @BotFather
1. Mở ứng dụng Telegram, tìm kiếm **`@BotFather`** (có dấu tích xanh chính chủ).
2. Gửi lệnh: `/newbot`
3. Nhập tên hiển thị cho bot (Ví dụ: `GBFS Bike Sharing Alert Bot`).
4. Nhập username kết thúc bằng `bot` (Ví dụ: `gbfs_bike_alert_bot`).
5. **@BotFather** sẽ trả về **`HTTP API Token`** (dạng `123456789:ABCdefGhIJKlmNoPQRstUVwxyZ`).
   * 👉 Đây chính là `TELEGRAM_BOT_TOKEN`.

### Bước 2: Lấy Chat ID cá nhân hoặc Group
1. Bấm vào link bot vừa tạo và bấm **Start** (`/start`) để mở cuộc trò chuyện với bot.
2. (Nếu muốn gửi vào Group): Thêm bot vào Group Telegram của bạn và cấp quyền gửi tin nhắn.
3. Mở trình duyệt hoặc dùng `curl` trên terminal máy chủ để gọi API `getUpdates`:
   ```bash
   curl -s "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getUpdates"
   ```
4. Tìm trường `"chat": {"id": 123456789, ...}` trong JSON trả về:
   * Nếu là chat cá nhân: Số dương (ví dụ: `987654321`).
   * Nếu là group: Số âm (ví dụ: `-1001234567890`).
   * 👉 Đây chính là `TELEGRAM_CHAT_ID`.

---

## 4. Kiểm tra kết nối Telegram từ máy chủ VM

### 1. Kiểm tra thông tin Bot (getMe):
```bash
curl -s "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getMe"
```
*Kết quả mẫu:* `{"ok":true,"result":{"id":...,"is_bot":true,"first_name":"GBFS Bike Sharing Alert Bot",...}}`

### 2. Gửi tin nhắn thử nghiệm (sendMessage):
```bash
curl -s -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{"chat_id": "<TELEGRAM_CHAT_ID>", "text": "🔔 Test Alert from GBFS Bike Sharing VM!"}'
```

---

## 5. Mẫu tin nhắn Telegram Alert

### Trường hợp Task thất bại (AIRFLOW_TASK_FAILURE):
```
🚨 Bike Sharing Pipeline Alert

Severity: ERROR
Type: AIRFLOW_TASK_FAILURE
DAG: hourly_mart_build_dag
Task: build_hourly_station_availability_task
Run ID: manual__2026-08-17T12:00:00+00:00
Time: 2026-08-17 19:30:00 UTC
Message: Task 'build_hourly_station_availability_task' in DAG 'hourly_mart_build_dag' failed: Database connection timed out
Log: http://<server-ip>:8080/log?dag_id=hourly_mart_build_dag&task_id=build_hourly_station_availability_task...
```

### Trường hợp Pipeline bị Stale / Lag quá hạn (PIPELINE_DAG_STALE):
```
⚠️ Bike Sharing Pipeline Alert

Severity: WARNING
Type: PIPELINE_DAG_STALE
DAG: station_status_snapshot_dag
Time: 2026-08-17 19:30:00 UTC
Message: Monitored pipeline 'station_status_snapshot_dag' status is STALE. Freshness lag is 95.0m exceeding SLA threshold 60m.
```

---

## 6. Bảng phân loại Mức độ nghiêm trọng & Trạng thái

### Mức độ nghiêm trọng (Severity):
| Severity | Định nghĩa | Trường hợp áp dụng |
| :--- | :--- | :--- |
| **`CRITICAL`** | Lỗi nghiêm trọng ảnh hưởng toàn bộ dữ liệu | Data Quality Critical check failed, DB corruption |
| **`ERROR`** | Task hoặc DAG chạy thất bại | Airflow Task Failure (`on_failure_callback`), DAG failed |
| **`WARNING`** | Dữ liệu bị chậm hoặc vi phạm cảnh báo | Pipeline bị `STALE` (vượt ngưỡng Freshness Lag), DQ Warning |
| **`INFO`** | Thông tin hệ thống / Khởi động lại | Thông báo audit, maintenance |

### Trạng thái Alert (Status & Notification Status):
| Status | Ý nghĩa |
| :--- | :--- |
| **`OPEN`** | Alert mới được tạo, đang chờ xử lý hoặc xem xét trên Dashboard |
| **`SENT`** | Đã gửi thông báo Telegram thành công |
| **`FAILED_TO_SEND`** | Gửi Telegram không thành công (lỗi mạng, sai token); alert vẫn lưu trong DB |
| **`SKIPPED`** | Bị bỏ qua do cơ chế Dedup (chống spam) hoặc thiếu cấu hình credentials |
| **`DISABLED`** | Webhook bị tắt trong cấu hình (`ALERT_WEBHOOK_ENABLED=false`) |

---

## 7. Các API Endpoints cho Dashboard

Tất cả các endpoint đều là **Read-Only**:

* **`GET /api/v1/alerts/stats`**: Thống kê tổng số active alerts phân loại theo `critical`, `error`, `warning`, `info`.
* **`GET /api/v1/alerts/active`**: Lấy danh sách alert đang mở (`OPEN` hoặc `FAILED_TO_SEND`), mặc định `limit=50`.
* **`GET /api/v1/alerts/latest`**: Lấy N alert mới nhất được ghi nhận trong DB, mặc định `limit=20`.
* **`GET /api/v1/alerts/history`**: Lịch sử alert có hỗ trợ phân trang (`limit`, `offset`) và bộ lọc (`severity`, `status`, `alert_type`, `dag_id`, `sort_by`, `sort_order`).

---

## 8. Hướng dẫn bật / tắt hệ thống Alerting

### Khi muốn bật thông báo Telegram:
1. Sửa `.env.prod`:
   ```bash
   ALERT_WEBHOOK_ENABLED=true
   ALERT_WEBHOOK_PROVIDER=telegram
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRstUVwxyZ
   TELEGRAM_CHAT_ID=987654321
   ```
2. Khởi động lại các container để nạp biến môi trường mới:
   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```

### Khi muốn tắt thông báo Telegram (chỉ lưu DB):
1. Sửa `.env.prod`:
   ```bash
   ALERT_WEBHOOK_ENABLED=false
   ```
2. Khởi động lại container:
   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```
