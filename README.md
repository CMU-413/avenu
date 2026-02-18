# Avenu

Full-stack web application with a React frontend, Flask backend API, dedicated Scheduler container, and MongoDB database.

---

## Repo Structure

```
├── frontend/        # React SPA build/runtime container
├── backend/         # Flask API + business logic + external integrations
├── scheduler/       # Scheduled job runner (HTTP client of backend)
├── docs/            # Architecture and API docs
├── docker-compose.yml
└── README.md
```

---

## Prerequisites

You need the following installed locally:

- Docker (with Docker Compose v2)
- Node.js (only if running frontend outside Docker)
- Python 3.11+ (only if running backend/scheduler outside Docker)

---

## Environment Variables

Create a `.env` file at the repo root (see `.env.sample`):

### Backend
- `MONGO_URI`
- `DB_NAME`
- `SECRET_KEY`
- `SESSION_COOKIE_SECURE`
- `FRONTEND_ORIGINS` (comma-separated origin allowlist for CORS)
- `SCHEDULER_INTERNAL_TOKEN` (shared secret for internal scheduler endpoint)
- `MS_GRAPH_TENANT_ID`
- `MS_GRAPH_CLIENT_ID`
- `MS_GRAPH_CLIENT_SECRET`
- `MS_GRAPH_SENDER_EMAIL`

### Frontend
- `VITE_API_BASE_URL` (default in compose: `http://localhost:8000`)

### Scheduler
- `BACKEND_API_URL` (must point to backend service DNS, default `http://backend:8000`)
- `SCHEDULER_INTERNAL_TOKEN` (must match backend)
- `SCHEDULER_CRON` (default `0 8 * * 1`)
- `SCHEDULER_TIMEZONE` (default `UTC`)
- `SCHEDULER_TICK_SECONDS` (default `20`)

---

## Running the App (Recommended: Docker)

From the repo root:

```bash
docker compose up --build
```

This starts four services:
- `frontend` on `http://localhost:8080`
- `backend` on `http://localhost:8000`
- `scheduler` (internal job runner container)
- `database` (MongoDB with persistent volume)

### Access

- Frontend: http://localhost:8080
- Backend health check: http://localhost:8000/health

---

## Running Without Docker

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PORT=8000 python app.py
```

Runs on: http://localhost:8000

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Runs on: http://localhost:5173

Set `VITE_API_BASE_URL` for local dev if backend is not on the default URL.

### Scheduler

```bash
cd scheduler
SCHEDULER_INTERNAL_TOKEN=<token> BACKEND_API_URL=http://localhost:8000 python main.py
```

## Notes

- Frontend environment variables are build-time and public.
- Backend environment variables are runtime and private.
- Scheduler is an internal backend API client and does not connect to MongoDB directly.
- Docker is the source of truth for prod and CI.
