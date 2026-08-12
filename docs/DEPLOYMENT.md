# Production Deployment Guide — GBFS Bike Sharing Operation Intelligence

This document provides a comprehensive, step-by-step guide for deploying the **GBFS Bike Sharing Operation Intelligence** platform onto an **Ubuntu VM/VPS** using **Docker Compose**.

---

## 1. Overview & Architecture

### System Topology

```
                   +-------------------------------------------------------------+
                   |                     Ubuntu VM / VPS                         |
                   |                                                             |
                   |  [Public Web Access]                                        |
                   |     Port 3000: React Dashboard (Nginx)                      |
                   |     Port 8000: FastAPI Read-Only Backend                    |
                   |     Port 8080: Apache Airflow Web UI                        |
                   |                                                             |
                   |  +-------------------------------------------------------+  |
                   |  |          Docker Internal Network (bike_network)       |  |
                   |  |                                                       |  |
                   |  |  +------------------+       +----------------------+  |  |
                   |  |  |  Frontend Nginx  | ----> |   FastAPI Service    |  |  |
                   |  |  |   (Port 80)      |       |     (Port 8000)      |  |  |
                   |  |  +------------------+       +----------+-----------+  |  |
                   |  |                                        |              |  |
                   |  |             +--------------------------+              |  |
                   |  |             |                          |              |  |
                   |  |             v                          v              |  |
                   |  |  +--------------------+     +----------------------+  |  |
                   |  |  |  PostgreSQL 15     |     |   Redis 7 (Cache)    |  |  |
                   |  |  |  (No public port)  |     |  (No public port)    |  |  |
                   |  |  +---------^----------+     +----------^-----------+  |  |
                   |  |            |                           |              |  |
                   |  |  +---------+---------------------------+-----------+  |  |
                   |  |  | Airflow Webserver & Scheduler (LocalExecutor)   |  |  |
                   |  |  +-------------------------------------------------+  |  |
                   |  +-------------------------------------------------------+  |
                   |                                                             |
                   |  [Persistent Named Volumes]                                 |
                   |     bike_postgres_data -> /var/lib/postgresql/data          |
                   |     bike_redis_data    -> /data                             |
                   |     bike_airflow_logs  -> /opt/airflow/logs                 |
                   +-------------------------------------------------------------+
```

### Key Production Principles
1. **Security Isolation**: PostgreSQL (`5432`) and Redis (`6379`) are strictly bound to the internal `bike_network` and are **never published** to the public internet.
2. **Read-Only Serving**: FastAPI operates exclusively in read-only mode over `mart` and `etl_metadata` schemas, with optional Redis query caching.
3. **Decoupled Orchestration**: Airflow Scheduler and Webserver run continuously to extract GBFS, Weather, and Calendar feeds, transform data, and populate mart tables.
4. **Static Frontend Hosting**: React SPA is compiled into optimized static assets and served via an Alpine Nginx container with HTML5 route fallback.
5. **Persistence**: All relational data and ETL logs reside in Docker named volumes, preserving state across container restarts and rebuilds.

---

## 2. Server Prerequisites

### Hardware Recommendations
- **OS**: Ubuntu 22.04 LTS / 24.04 LTS (x86_64 / amd64)
- **CPU**: 2 vCPUs minimum (4 vCPUs recommended)
- **RAM**: 4 GB minimum (8 GB recommended for full pipeline runs)
- **Storage**: 25 GB+ SSD storage

### Firewall Configuration (UFW)
Open only required public ports:
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp     # SSH Access
sudo ufw allow 3000/tcp   # React Dashboard
sudo ufw allow 8000/tcp   # FastAPI Documentation & Endpoints
sudo ufw allow 8080/tcp   # Airflow Web UI
sudo ufw enable
```

---

## 3. Docker Engine & Compose Installation on Ubuntu

Run the following commands on your Ubuntu server to install Docker Engine and the Docker Compose plugin:

```bash
# 1. Update package index and install prerequisites
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release

# 2. Add Docker official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# 3. Set up repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 4. Install Docker Engine and Compose Plugin
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 5. Enable and start Docker service
sudo systemctl enable docker
sudo systemctl start docker

# 6. (Optional) Allow current user to run Docker without sudo
sudo usermod -aG docker $USER
# Log out and log back in for group changes to take effect
```

---

## 4. Deployment Steps

### Step 1: Clone Repository
```bash
git clone https://github.com/HoangMinh1005/Bike_sharing.git
cd Bike_sharing
```

### Step 2: Configure Production Environment (`.env.prod`)
Copy the environment template:
```bash
cp .env.example .env.prod
```

Edit `.env.prod` using your preferred editor (`nano .env.prod` or `vim .env.prod`):
```ini
# ==========================================
# Database Configuration
# ==========================================
POSTGRES_USER=postgres
POSTGRES_PASSWORD=SetAStrongRandomPassword123!
POSTGRES_DB=bike_sharing

# App Database URL (Inside Docker network, use hostname postgres:5432)
DATABASE_URL=postgresql+psycopg2://postgres:SetAStrongRandomPassword123!@postgres:5432/bike_sharing

# Redis URL (Inside Docker network, use hostname redis:6379)
REDIS_URL=redis://redis:6379/0

# ==========================================
# Airflow Credentials & Configuration
# ==========================================
AIRFLOW_USERNAME=admin
AIRFLOW_PASSWORD=SetAStrongAirflowPassword123!
AIRFLOW_UID=50000

# ==========================================
# External Data Feeds
# ==========================================
GBFS_BASE_URL=https://gbfs.lyft.com/gbfs/2.3/bkn/en
GBFS_LANGUAGE=en

# ==========================================
# Exposed Ports
# ==========================================
FASTAPI_PORT=8000
FRONTEND_PORT=3000
AIRFLOW_WEBSERVER_PORT=8080

# ==========================================
# CORS & Frontend Build Configuration
# Replace <server-ip> with your actual VM public IP or domain name
# ==========================================
FRONTEND_ORIGINS=http://localhost:3000,http://<server-ip>:3000
VITE_API_BASE_URL=http://<server-ip>:8000/api/v1
```

> [!IMPORTANT]
> **Vite Build-Time Environment Variable**: `VITE_API_BASE_URL` is baked into client-side JavaScript bundle during `docker compose build`. If you change your server's public IP or domain, you must rebuild the frontend container:
> `docker compose -f docker-compose.prod.yml --env-file .env.prod build --no-cache frontend && docker compose -f docker-compose.prod.yml --env-file .env.prod up -d frontend`

### Step 3: Build and Launch Services
Start the entire stack in detached mode:
```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

### Step 4: Initialize Database Schemas
Run the automated schema initialization script to create schemas, raw tables, staging tables, data marts, metadata tables, and performance indexes:
```bash
bash scripts/init_project_db.sh
```

---

## 5. Verification & Health Checks

### Check Container Status
```bash
docker compose -f docker-compose.prod.yml ps
```
All containers (`bike_postgres`, `bike_redis`, `bike_airflow_webserver`, `bike_airflow_scheduler`, `bike_fastapi`, `bike_frontend`) should show state `Up` or `healthy`.

### Verify FastAPI Health Endpoint
```bash
curl http://localhost:8000/api/v1/health
```
Expected JSON response:
```json
{
  "status": "healthy",
  "database": "connected",
  "cache": "connected",
  "version": "1.0.0"
}
```

### Accessing Web Interfaces
- **React Dashboard**: Open `http://<server-ip>:3000` in your web browser.
- **FastAPI Interactive Docs**: Open `http://<server-ip>:8000/docs`.
- **Airflow Web UI**: Open `http://<server-ip>:8080` (Log in with `AIRFLOW_USERNAME` and `AIRFLOW_PASSWORD`).

---

## 6. Initial Airflow DAG Execution Order

When running for the first time on a fresh database, trigger the DAGs in the following sequential order via the Airflow UI (`http://<server-ip>:8080`) or CLI:

```bash
# 1. Metadata DAG: Ingests station & region metadata
docker compose -f docker-compose.prod.yml exec airflow-webserver airflow dags trigger gbfs_metadata_daily_dag

# 2. Snapshot DAG: Ingests real-time bike & dock availability snapshots
docker compose -f docker-compose.prod.yml exec airflow-webserver airflow dags trigger station_status_snapshot_dag

# 3. Weather & Calendar DAG: Ingests weather forecast & calendar holidays
docker compose -f docker-compose.prod.yml exec airflow-webserver airflow dags trigger weather_calendar_sync_dag

# 4. Hourly Mart DAG: Computes hourly mobility aggregations
docker compose -f docker-compose.prod.yml exec airflow-webserver airflow dags trigger hourly_mart_build_dag

# 5. Daily Summary DAG: Computes system, region, and station daily summaries
docker compose -f docker-compose.prod.yml exec airflow-webserver airflow dags trigger daily_summary_dag

# 6. Pipeline Health DAG: Evaluates SLA, data freshness, and data volume
docker compose -f docker-compose.prod.yml exec airflow-webserver airflow dags trigger pipeline_health_dag
```

---

## 7. Verifying Data in PostgreSQL

Inspect table counts in PostgreSQL to ensure the pipeline ingested and processed records:

```bash
# Open interactive psql session
docker compose -f docker-compose.prod.yml exec postgres psql -U postgres -d bike_sharing
```

Run SQL queries:
```sql
-- Check Raw Layer
SELECT COUNT(*) FROM raw.gbfs_station_information;
SELECT COUNT(*) FROM raw.gbfs_station_status;

-- Check Staging Layer
SELECT COUNT(*) FROM staging.stg_stations;
SELECT COUNT(*) FROM staging.stg_station_status_snapshots;

-- Check Data Marts Layer
SELECT COUNT(*) FROM mart.daily_system_summary;
SELECT COUNT(*) FROM mart.daily_station_summary;
SELECT COUNT(*) FROM mart.daily_region_summary;
SELECT COUNT(*) FROM mart.weather_mobility_summary;

-- Check Pipeline Health Metadata
SELECT dag_id, pipeline_status, latest_data_timestamp FROM etl_metadata.pipeline_health_summary;
```

---

## 8. Backup and Restore Procedures

### Database Backup
Run the backup script anytime to produce a timestamped SQL dump in the `backups/` directory:
```bash
bash scripts/backup_postgres.sh
```
Output:
```text
==========================================================
Starting PostgreSQL Backup
Database:  bike_sharing
User:      postgres
Output:    /path/to/Bike_sharing/backups/backup_bike_sharing_20260811_120000.sql
==========================================================
Backup completed successfully!
File: backups/backup_bike_sharing_20260811_120000.sql (12MB)
==========================================================
```

### Database Restore
Restore the database from a specific backup dump:
```bash
bash scripts/restore_postgres.sh backups/backup_bike_sharing_20260811_120000.sql
```

### Automated Daily Backup via Cron
To automate backups every day at 02:00 AM, add a crontab entry:
```bash
crontab -e
```
Add the line:
```cron
0 2 * * * cd /home/ubuntu/Bike_sharing && /bin/bash scripts/backup_postgres.sh >> /home/ubuntu/Bike_sharing/logs/backup.log 2>&1
```

---

## 9. Troubleshooting & Common Issues

| Issue / Symptom | Root Cause | Solution |
| :--- | :--- | :--- |
| **Frontend displays "Could not load data"** | `VITE_API_BASE_URL` in `.env.prod` is set to `localhost` or invalid IP. | Update `VITE_API_BASE_URL=http://<server-ip>:8000/api/v1` in `.env.prod`, then rebuild: `docker compose -f docker-compose.prod.yml --env-file .env.prod build frontend && docker compose -f docker-compose.prod.yml up -d frontend`. |
| **CORS error in browser console** | `FRONTEND_ORIGINS` does not include client origin. | Add `http://<server-ip>:3000` to `FRONTEND_ORIGINS` in `.env.prod` and restart FastAPI: `docker compose -f docker-compose.prod.yml restart fastapi`. |
| **Airflow UI shows "Scheduler is not running"** | Scheduler container crashed or exceeded memory limit. | Inspect logs: `docker compose -f docker-compose.prod.yml logs -f airflow-scheduler`. Restart scheduler: `docker compose -f docker-compose.prod.yml restart airflow-scheduler`. |
| **Database connection refused** | Container trying to connect to `localhost:5432` instead of `postgres:5432`. | Ensure all connection strings inside Docker use `postgres:5432` and `redis:6379`. |
| **Port already in use error** | Host port `8000`, `3000`, or `8080` is occupied by another process. | Change `FASTAPI_PORT`, `FRONTEND_PORT`, or `AIRFLOW_WEBSERVER_PORT` in `.env.prod`. |

> [!CAUTION]
> **Data Loss Warning**: Never run `docker compose down -v` on production servers. The `-v` flag will permanently destroy the `bike_postgres_data` volume containing your database records. Use `docker compose -f docker-compose.prod.yml down` without `-v`.

---

## 10. Useful Management Commands

```bash
# View live logs of all services
docker compose -f docker-compose.prod.yml logs -f

# View live logs of a specific service
docker compose -f docker-compose.prod.yml logs -f fastapi
docker compose -f docker-compose.prod.yml logs -f airflow-scheduler

# Restart a specific service
docker compose -f docker-compose.prod.yml restart fastapi

# Stop all services cleanly (preserves volumes)
docker compose -f docker-compose.prod.yml stop

# Start all services
docker compose -f docker-compose.prod.yml start
```
