# Production Nginx Reverse Proxy & HTTPS Let's Encrypt Setup Guide

Hướng dẫn chi tiết thiết lập lớp **Nginx Reverse Proxy**, kích hoạt **HTTPS bảo mật với Let's Encrypt (Certbot)**, và cấu hình tường lửa **Azure Network Security Group (NSG)** cho hệ thống **GBFS Bike Sharing Operation Intelligence**.

---

## 1. Tổng quan Kiến trúc Deployment

Hệ thống được thiết kế theo dạng **Modular (Ghép nối linh hoạt)**, hỗ trợ song song 3 chế độ vận hành:

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ MODE A: Direct Port Demo (Mặc định - Fallback)                                              │
│   - http://<public-ip>:3000   -> React Dashboard                                            │
│   - http://<public-ip>:8000   -> FastAPI REST API                                           │
│   - http://<public-ip>:8080   -> Airflow Web UI                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
                                                │ (Nâng cấp)
                                                ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ MODE B: Nginx HTTP Reverse Proxy (Cổng tập trung Port 80)                                   │
│   - http://<domain-or-ip>/        -> React Dashboard (Frontend)                             │
│   - http://<domain-or-ip>/api/... -> FastAPI REST API                                       │
│   - http://<domain-or-ip>/docs    -> Swagger API Documentation                              │
│   - http://<domain-or-ip>/airflow -> Airflow Web UI                                         │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
                                                │ (Kích hoạt SSL)
                                                ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ MODE C: Production HTTPS với Let's Encrypt (Cổng an toàn Port 443 + Chuyển hướng HTTP 80)    │
│   - https://yourdomain.com/        -> React Dashboard (SSL/TLS mã hóa)                      │
│   - https://yourdomain.com/api/... -> FastAPI REST API                                      │
│   - https://yourdomain.com/docs    -> Swagger Documentation                                 │
│   - http://yourdomain.com/*        -> Tự động redirect 301 sang https://...                 │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Bảng Phân Quyền Tường Lửa Azure NSG (Inbound Security Rules)

Để đảm bảo an toàn tuyệt đối cho hệ thống, áp dụng bảng quy tắc mở/đóng cổng trên Azure Network Security Group (NSG) như sau:

| Port | Giao thức | Trước khi có Nginx (Mode A) | Sau khi có Nginx / HTTPS (Mode B & C) | Ghi chú an toàn |
| :--- | :--- | :--- | :--- | :--- |
| **`22`** | TCP (SSH) | **`My IP`** | **`My IP`** | Tuyệt đối không mở `Any` để tránh brute-force |
| **`80`** | TCP (HTTP) | Closed | **`Any` (Internet)** | Dùng cho Web traffic & Let's Encrypt challenge |
| **`443`** | TCP (HTTPS) | Closed | **`Any` (Internet)** | Dùng cho Web traffic mã hóa SSL/TLS |
| **`3000`** | TCP (Frontend) | `Any` (Demo) | **`Closed`** | Nginx forward nội bộ qua `frontend:80` |
| **`8000`** | TCP (FastAPI) | `Any` (Demo) | **`Closed`** | Nginx forward nội bộ qua `fastapi:8000` |
| **`8080`** | TCP (Airflow) | `My IP` | **`Closed`** hoặc **`My IP`** | Tránh public rộng rãi Airflow ra ngoài |
| **`5432`** | TCP (Postgres) | **`Closed`** | **`Closed`** | **KHÔNG BAO GIỜ MỞ PUBLIC** |
| **`6379`** | TCP (Redis) | **`Closed`** | **`Closed`** | **KHÔNG BAO GIỜ MỞ PUBLIC** |

---

## 3. Hướng dẫn Triển khai theo từng Chế độ

### 🅰️ MODE A: Chạy chế độ Direct Port Demo (Hiện tại)

Nếu bạn chỉ muốn demo nhanh qua các cổng trực tiếp:

1. **Cấu hình `.env.prod`**:
   ```bash
   VITE_API_BASE_URL=http://<public-ip>:8000/api/v1
   FRONTEND_ORIGINS=http://localhost:3000,http://<public-ip>:3000
   ```
2. **Khởi động**:
   ```bash
   docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
   ```
3. **Truy cập**:
   * Dashboard: `http://<public-ip>:3000`
   * FastAPI Docs: `http://<public-ip>:8000/docs`
   * Airflow: `http://<public-ip>:8080`

---

### 🅱️ MODE B: Chạy chế độ Nginx Reverse Proxy (HTTP Port 80)

Gom toàn bộ dịch vụ về một cổng duy nhất (Port 80):

1. **Cấu hình `.env.prod`**:
   ```bash
   # Đặt API Base URL về đường dẫn tương đối
   VITE_API_BASE_URL=/api/v1
   FRONTEND_ORIGINS=http://<public-ip>,http://localhost
   HTTP_PORT=80
   HTTPS_PORT=443
   ```
2. **Build lại Frontend để nhận API base URL tương đối**:
   ```bash
   docker compose -f docker-compose.prod.yml build frontend
   ```
3. **Khởi động Nginx kèm toàn bộ hệ thống**:
   ```bash
   docker compose -f docker-compose.prod.yml -f docker-compose.nginx.yml --env-file .env.prod up -d
   ```
4. **Truy cập qua Port 80**:
   * Dashboard: `http://<public-ip>/`
   * FastAPI Docs: `http://<public-ip>/docs`
   * API Health: `http://<public-ip>/api/v1/health`

---

### 🔒 MODE C: Cấu hình Domain & HTTPS với Let's Encrypt (Production)

Khi bạn đã có tên miền riêng (ví dụ `bike.yourdomain.com`):

#### Bước 1: Trỏ DNS A Record về IP của Azure VM
1. Truy cập trang quản trị DNS của nhà cung cấp tên miền (Cloudflare, Namecheap, GoDaddy...).
2. Thêm bản ghi:
   * **Type**: `A`
   * **Name / Host**: `@` (hoặc subdomain `bike`)
   * **Value / IP**: `<Public_IP_Azure_VM>`
   * **TTL**: Auto hoặc 300s
3. Chờ DNS lan truyền (kiểm tra bằng lệnh `ping yourdomain.com` hoặc `nslookup yourdomain.com`).

---

#### Bước 2: Mở Port 80 và 443 trên Azure VM NSG
1. Mở Azure Portal $\to$ Chọn **Virtual Machine** $\to$ **Networking (hoặc Network Security Group)**.
2. Thêm **Inbound Port Rules**:
   * **HTTP**: Destination Port `80`, Protocol `TCP`, Action `Allow`, Priority `300`.
   * **HTTPS**: Destination Port `443`, Protocol `TCP`, Action `Allow`, Priority `310`.

---

#### Bước 3: Đảm bảo Nginx đang chạy ở Port 80 (để phục vụ xác thực ACME)
```bash
docker compose -f docker-compose.prod.yml -f docker-compose.nginx.yml --env-file .env.prod up -d nginx
```

---

#### Bước 4: Chạy Certbot để lấy Chứng chỉ SSL
Chạy container `certbot` một lần để xác thực tên miền qua webroot challenge:

```bash
docker run -it --rm \
  -v $(pwd)/docker/nginx/certbot/conf:/etc/letsencrypt \
  -v $(pwd)/docker/nginx/certbot/www:/var/www/certbot \
  certbot/certbot certonly \
  --webroot \
  --webroot-path /var/www/certbot \
  --email your-email@example.com \
  --agree-tos \
  --no-eff-email \
  -d yourdomain.com -d www.yourdomain.com
```

> 💡 *Certbot sẽ tạo chứng chỉ SSL tại `docker/nginx/certbot/conf/live/yourdomain.com/`*.

---

#### Bước 5: Kích hoạt file cấu hình SSL cho Nginx
1. Tạo file cấu hình SSL từ template mẫu:
   ```bash
   cp docker/nginx/conf.d/app.ssl.conf.template docker/nginx/conf.d/app.conf
   ```
2. Thay thế tên miền `yourdomain.com` bằng tên miền thật của bạn:
   ```bash
   sed -i 's/yourdomain.com/tenmien_that_cua_ban.com/g' docker/nginx/conf.d/app.conf
   ```
3. Cập nhật biến môi trường trong `.env.prod`:
   ```bash
   PUBLIC_DOMAIN=tenmien_that_cua_ban.com
   FRONTEND_ORIGINS=https://tenmien_that_cua_ban.com
   VITE_API_BASE_URL=/api/v1
   ```
4. Build lại frontend và reload Nginx:
   ```bash
   docker compose -f docker-compose.prod.yml build frontend
   docker compose -f docker-compose.prod.yml -f docker-compose.nginx.yml --env-file .env.prod up -d
   docker compose -f docker-compose.prod.yml -f docker-compose.nginx.yml exec nginx nginx -s reload
   ```

---

#### Bước 6: Thiết lập Tự động Gia hạn Chứng chỉ (Auto-Renewal Cron Job)
Chứng chỉ Let's Encrypt có hạn 90 ngày. Thiết lập cron job tự động gia hạn vào 02:00 sáng mỗi đầu tuần:

1. Mở crontab trên máy chủ VM:
   ```bash
   crontab -e
   ```
2. Thêm dòng sau vào cuối file:
   ```bash
   0 2 * * 1 docker run --rm -v /home/azureuser/Bike_sharing/docker/nginx/certbot/conf:/etc/letsencrypt -v /home/azureuser/Bike_sharing/docker/nginx/certbot/www:/var/www/certbot certbot/certbot renew --webroot -w /var/www/certbot --quiet && cd /home/azureuser/Bike_sharing && docker compose -f docker-compose.prod.yml -f docker-compose.nginx.yml exec -T nginx nginx -s reload
   ```

---

## 4. Các Giải pháp Bảo vệ Airflow Web UI

Airflow Web UI là công cụ quản trị hệ thống quan trọng, không nên public mở cho toàn bộ Internet. Có 3 giải pháp bảo vệ:

### 🛡️ Giải pháp 1 (Khuyến nghị): Giữ Airflow ở Port 8080 và Giới hạn IP trên Azure NSG
* Không đưa Airflow vào Nginx public.
* Giữ cấu hình port `8080:8080` trong `docker-compose.prod.yml`.
* Trên Azure NSG, chỉ tạo Inbound Rule cho Port `8080` với **Source IP = `My IP`** (Địa chỉ IP tĩnh của máy tính bạn).

### 🛡️ Giải pháp 2: Sử dụng Nginx Basic Authentication cho `/airflow/`
Nếu muốn truy cập qua Nginx nhưng yêu cầu mật khẩu lớp ngoài:
1. Cài đặt tiện ích tạo mật khẩu:
   ```bash
   sudo apt-get install -y apache2-utils
   htpasswd -c ./docker/nginx/.htpasswd airflow_admin
   ```
2. Thêm vào block `location /airflow/` trong `docker/nginx/conf.d/app.conf`:
   ```nginx
   auth_basic "Airflow Restricted Access";
   auth_basic_user_file /etc/nginx/.htpasswd;
   ```
3. Mount file `.htpasswd` vào Nginx container trong `docker-compose.nginx.yml`.

### 🛡️ Giải pháp 3: Sử dụng Subdomain riêng (`airflow.yourdomain.com`)
* Tách biệt hoàn toàn Dashboard (`bike.yourdomain.com`) và Airflow (`airflow.yourdomain.com`).
* Tránh được các vấn đề xung đột đường dẫn tĩnh (static assets subpath) của Airflow.

---

## 5. Xử lý sự cố (Troubleshooting)

1. **Kiểm tra trạng thái Nginx**:
   ```bash
   docker compose -f docker-compose.prod.yml -f docker-compose.nginx.yml logs nginx
   ```
2. **Kiểm tra cú pháp file config Nginx**:
   ```bash
   docker compose -f docker-compose.prod.yml -f docker-compose.nginx.yml exec nginx nginx -t
   ```
3. **Nạp lại cấu hình Nginx không cần restart container**:
   ```bash
   docker compose -f docker-compose.prod.yml -f docker-compose.nginx.yml exec nginx nginx -s reload
   ```
