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
│   ├── api/          # Axios API clients for health, system, stations, regions, ranking, pipelines
│   ├── components/   # UI layout, common cards, Recharts chart cards, responsive data tables
│   ├── hooks/        # TanStack Query custom hooks
│   ├── pages/        # 7 React dashboard page views
│   ├── routes/       # React Router DOM route definitions
│   ├── types/        # TypeScript schemas matching FastAPI backend responses
│   └── utils/        # Formatters, date helpers, and UI constants
├── Dockerfile        # Multi-stage build (node:20-alpine -> nginx:alpine)
├── nginx.conf        # Nginx SPA fallback configuration
└── vite.config.ts    # Vite bundler configuration
```
