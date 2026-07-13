# Bike Sharing Operation Intelligence

Hệ thống Data Engineering & Analytics thông minh phục vụ việc giám sát, cảnh báo và điều phối hoạt động xe đạp công cộng dựa trên đặc tả tiêu chuẩn dữ liệu mở **GBFS (General Bikeshare Feed Specification)**.

Hệ thống thực hiện thu thập tự động dữ liệu từ các trạm xe đạp, kết hợp với các dữ liệu ngoại tác như thời tiết (Weather API) và lịch trình làm việc (Calendar CSV) để phân tích mức độ cân bằng cung cầu, phát hiện bất thường hoạt động, và sinh các đề xuất tái cân bằng (rebalancing) tối ưu thời gian thực.

---

## 1. Bản đồ Tài liệu dự án (Documentation Map)

Để hiểu rõ hơn chi tiết thiết kế hệ thống, vui lòng tham khảo các tài liệu chuyên đề dưới đây:

* 📄 **[Yêu cầu Nghiệp vụ (Business Requirements)](docs/01_business_requirement.md)**: Định nghĩa mục tiêu vận hành, downstream consumers, công thức tính toán chỉ số (`demand_score`, `empty_rate`, `full_rate`) và các cấp độ khả dụng.
* 📄 **[Phân tích Nguồn Dữ liệu (Data Source Analysis)](docs/02_data_source_analysis.md)**: Chi tiết cấu trúc các endpoint GBFS đầu vào, cơ chế dữ liệu thời tiết và lịch trình bổ trợ.
* 📄 **[Mô hình Cơ sở Dữ liệu (Data Model Design)](docs/03_data_model_design.md)**: Chi tiết hóa thiết kế schema cơ sở dữ liệu vật lý phân tầng Raw, Staging, Mart trên PostgreSQL, bao gồm cả cơ chế tối ưu index và phân mảnh (partitioning).
* 📄 **[Thiết kế Điều phối DAG (DAG Design & Orchestration)](docs/04_dag_design.md)**: Đặc tả chi tiết 8 luồng công việc tự động (DAGs) chạy định kỳ điều phối bởi Apache Airflow.
* 📄 **[Phân tích Thiết kế Tổng quan (System Design Overview)](/home/minhvh/.gemini/antigravity-ide/brain/e0f9c848-5dea-4b60-9d85-003f158bfbd7/system_design_analysis.md)**: Tổng quan kiến trúc hệ thống dữ liệu và thiết kế caching lớp API.

---

## 2. Kiến trúc thư mục dự án (Project Structure)

Dự án được tổ chức theo cấu trúc module hóa phân tách trách nhiệm rõ ràng:

```text
bike-sharing-operation-intelligence/
├── api/                     # Cổng phục vụ dữ liệu (FastAPI app)
│   ├── routes/              # Các routes REST API (stations, regions, alerts...)
│   ├── schemas/             # Pydantic schemas định nghĩa API contracts
│   └── services/            # Lớp nghiệp vụ truy vấn database và xử lý logic
├── dags/                    # Nơi chứa các file DAG định nghĩa luồng Airflow
├── data/                    # Thư mục lưu trữ dữ liệu tĩnh (lịch) và dữ liệu mẫu
├── docker/                  # Cấu hình Dockerfile tùy biến cho các dịch vụ
│   └── airflow/             # Dockerfile build môi trường chạy độc lập cho Airflow
├── docs/                    # Tài liệu đặc tả kỹ thuật và thiết kế
├── logs/                    # Nơi lưu trữ log của Airflow và API
├── scripts/                 # Các script shell hỗ trợ khởi tạo, kiểm thử nhanh
├── sql/                     # Chứa toàn bộ mã nguồn SQL biến đổi dữ liệu
│   ├── backfill/            # SQL hỗ trợ chạy lại dữ liệu quá khứ
│   ├── build_mart/          # SQL tổng hợp dữ liệu tầng Mart
│   ├── dq/                  # SQL chạy kiểm tra chất lượng dữ liệu
│   ├── init/                # SQL khởi tạo cấu trúc cơ sở dữ liệu ban đầu
│   ├── raw_to_staging/      # SQL parse dữ liệu từ thô sang staging
│   └── retention/           # SQL dọn dẹp dữ liệu cũ định kỳ
├── src/                     # Mã nguồn Python xử lý cốt lõi của pipeline
│   ├── backfill/            # Dịch vụ backfill dữ liệu staging/mart
│   ├── cache/               # Logic quản lý cache (FastAPI memory / Redis)
│   ├── common/              # Các cấu hình chung, kết nối DB, logger, time utils
│   ├── extract/             # Logic kết nối API kéo dữ liệu GBFS/Thời tiết
│   ├── load/                # Logic tải dữ liệu thô vào DB
│   ├── mart/                # Lớp Python wrapper tổng hợp dữ liệu mart
│   ├── metadata/            # Theo dõi trạng thái, watermark, health pipeline
│   ├── operation/           # Thuật toán phát hiện bất thường, rebalance
│   ├── quality/             # Trình kiểm tra dữ liệu tự động (Data Quality)
│   ├── retention/           # Dịch vụ dọn dẹp dữ liệu lưu trữ
│   └── transform/           # Lớp Python điều phối các file SQL biến đổi dữ liệu
└── tests/                   # Thư mục kiểm thử (Unit, Integration tests)
```

---

## 3. Hướng dẫn Khởi chạy Hệ thống

Hệ thống được ảo hóa hoàn toàn bằng Docker Compose để đảm bảo môi trường phát triển nhất quán.

### Bước 1: Chuẩn bị biến môi trường
Sao chép file cấu hình môi trường mẫu và tùy chỉnh (nếu cần):
```bash
cp .env.example .env
```

### Bước 2: Dọn dẹp tài nguyên cũ (nếu có)
Xóa bỏ các container và volume cũ để tránh xung đột dữ liệu:
```bash
docker compose down -v
```

### Bước 3: Build lại các Docker Image
Build lại các service với dependencies đã được tách biệt (FastAPI chạy Python 3.11, Airflow chạy Python 3.10):
```bash
docker compose build --no-cache
```

### Bước 4: Khởi tạo Cơ sở dữ liệu Airflow
Khởi chạy dịch vụ khởi tạo để migrate database và tạo tài khoản quản trị Admin:
```bash
docker compose up airflow-init
```

### Bước 5: Khởi chạy toàn bộ hệ thống
Bật tất cả các dịch vụ ở chế độ background:
```bash
docker compose up -d
```

---

## 4. Các Cổng Dịch vụ Mặc định

Sau khi khởi chạy thành công, các dịch vụ sẽ khả dụng tại các địa chỉ sau:

* **Airflow Web UI**: [http://localhost:8080](http://localhost:8080) (Tài khoản: `admin` / Mật khẩu: `admin`)
* **FastAPI Swagger API**: [http://localhost:8000/docs](http://localhost:8000/docs) (Xem tài liệu API và test trực tiếp các endpoint)
* **pgAdmin (Database UI)**: [http://localhost:5050](http://localhost:5050) (Tài khoản: `admin@admin.com` / Mật khẩu: `admin`)
  * *Hướng dẫn kết nối database*: Tạo máy chủ mới trong pgAdmin với host là `postgres`, port `5432`, username `postgres`, password `postgres`.
