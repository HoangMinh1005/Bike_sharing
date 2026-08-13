# React Dashboard Frontend — Bike Sharing Operation Intelligence

Standalone read-only operational dashboard built with **React 18**, **TypeScript**, **Vite**, **Tailwind CSS**, **TanStack Query**, and **Recharts**.

---

## 1. Features & Architecture

- **Read-only Dashboard**: Consumes read-only REST API endpoints exposed by FastAPI backend (`/api/v1`).
- **Zero Database/Airflow Mutation**: No direct PostgreSQL queries, no Airflow DAG triggers, no data writes or deletes.
- **7 Operational Pages**:
  1. **Overview (`/`)**: System-wide daily/hourly mobility metrics, availability trends, and weather correlations.
  2. **Stations (`/stations`)**: Station availability table, keyword search, sort options, and availability rankings.
  3. **Station Detail (`/stations/:stationId`)**: Station capacity, 24-hour observation bucket charts, and historical trends.
  4. **Regions (`/regions`)**: Regional station distribution, regional availability comparison, and high demand station counts.
  5. **Region Detail (`/regions/:regionId`)**: Detailed regional performance history and regional stations table.
  6. **Demand Ranking (`/ranking`)**: Station demand classifications (`HIGH`, `MEDIUM`, `LOW`), top demand spotlight cards, and ranking score charts.
  7. **Pipeline Health (`/pipelines`)**: SLA freshness lag metrics, monitored DAG health statuses, Data Quality check summaries, and recent execution logs.

---

## 2. Environment Variables

Create `.env` in `frontend/` directory (or use `.env.example` as a template):

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

If `VITE_API_BASE_URL` is omitted, the frontend automatically falls back to `http://localhost:8000/api/v1`.

---

## 3. Local Development

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start Vite development server (listening on http://localhost:5173)
npm run dev
```

---

## 4. Production Build & Linting

```bash
# Run TypeScript compilation and Vite build
npm run build

# Preview production build locally
npm run preview
```

---

## 5. Docker Deployment

Build and run using Docker:

```bash
# Build Docker image
docker build -t bike-frontend ./frontend

# Run container on port 3000
docker run -p 3000:80 bike-frontend
```

Using Docker Compose:

```bash
docker compose up -d frontend
```

---

## 6. Project Structure

```text
frontend/
├── src/
│   ├── api/          # Axios API clients for freshness, health, system, stations, regions, ranking, pipelines
│   ├── components/   # UI layout, common state cards (EmptyState, ErrorState, PartialDataWarning, DataUnavailableState), chart cards, data tables
│   ├── hooks/        # TanStack Query custom hooks
│   ├── pages/        # 7 React dashboard page views
│   ├── routes/       # React Router DOM route definitions
│   ├── types/        # TypeScript schemas matching FastAPI backend responses
│   └── utils/        # Error parsing, formatters, date helpers, and UI constants
├── Dockerfile        # Multi-stage build (node:20-alpine -> nginx:alpine)
├── nginx.conf        # Nginx SPA fallback configuration
└── vite.config.ts    # Vite bundler configuration
```

---

## 7. Dashboard State Hierarchy & Initial Deployment Behavior

### A. "API Online" vs "Data Available"
- **API Online (`/api/v1/health`)**: Indicates the FastAPI service and connection to PostgreSQL / Redis are active and responsive.
- **Data Freshness (`/api/v1/freshness/summary`)**: Indicates whether real-time data feeds and marts have actually ingested observations and completed their ETL cycles.
- *An API can be 100% online while certain analytical tables are still accumulating data.*

### B. State Classification Matrix

| State Type | Trigger Scenario | Visual Appearance | Meaning & Recommended Action |
| :--- | :--- | :--- | :--- |
| **API Unavailable** | Network error or API container stopped | Rose Error Card (Severity: `error`) | Check if `fastapi` container is running (`docker compose ps`). |
| **Backend Query Error** | HTTP 500 server exception | Rose Error Card with collapsible tech details | Check backend logs and PostgreSQL schema integrity. |
| **Partial Data** | Hourly data exists, but daily summary is pending | Amber Alert Banner (Severity: `warning`) | Hourly metrics are visible; daily aggregations will generate at midnight. |
| **Data Pending / Not Ready** | Fresh deployment before first ETL cycle | Slate / Amber Info Card (Severity: `info`) | DAGs are actively processing; data will appear upon task completion. |
| **Empty Search / Filter** | No matching station for user query | Gentle Inbox Empty Card (Severity: `info`) | Adjust search keywords or date range filters. |

### C. Expected Timeline After Initial Server Deployment
1. **0 - 5 minutes**: `station_status_snapshot_dag` fetches the first GBFS station status batch. Station snapshot metrics become Live.
2. **1 - 2 hours**: `hourly_mart_build_dag` builds the first hourly mobility records. Hourly charts populate.
3. **24 hours**: `daily_summary_dag` computes complete 24-hour daily availability and station demand rankings. Daily summary KPIs and ranking tables become fully active.

