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

Copy `.env.sample` into `.env` and fill out the required values.

Notes:
- `SECRET_KEY` is required outside tests.
- In testing mode (`FLASK_TESTING=true`), notifications use console providers for email and SMS.
- Outside testing mode, notifications use Microsoft Graph for email and Twilio for SMS and require all `MS_GRAPH_*` and `TWILIO_*` values.
- Required backend notification vars outside testing:
  - `MS_GRAPH_TENANT_ID`
  - `MS_GRAPH_CLIENT_ID`
  - `MS_GRAPH_CLIENT_SECRET`
  - `MS_GRAPH_SENDER_EMAIL`
  - `TWILIO_ACCOUNT_SID`
  - `TWILIO_AUTH_TOKEN`
  - `TWILIO_PHONE_NUMBER`
- For iframe/Canvas embedding, set:
  - `SESSION_COOKIE_SAMESITE=None`
  - `SESSION_COOKIE_SECURE=true`
  - optional: `SESSION_COOKIE_PARTITIONED=true`
- User sessions are created via `POST /api/session/login` with a user email.
- `POST /api/session/logout` clears the session.
- Admin routes authorize by loading `session["user_id"]` from DB and requiring `user.isAdmin == true`.
- `FRONTEND_ORIGINS` (comma-separated origin allowlist for CORS)
- `SCHEDULER_INTERNAL_TOKEN` (shared secret for internal scheduler endpoint)

### Frontend
- `VITE_BASE_PATH` (default in compose: `/mail/`)
- `VITE_API_BASE_URL` (default in compose: `/mail/api`)

### Scheduler
- `BACKEND_API_URL` (must point to backend service DNS, default `http://backend:8000`)
- `SCHEDULER_INTERNAL_TOKEN` (must match backend)
- `SCHEDULER_CRON` (default `0 8 * * 1`, i.e. 8 AM on Monday)
- `SCHEDULER_TIMEZONE` (default `America/New_York`)
- `SCHEDULER_TICK_SECONDS` (default `20`)

---

## Running the App (Recommended: Docker)

From the repo root:

```bash
docker compose up --build
```

This starts four services:
- `frontend` on `http://localhost:8080/mail`
- `backend` (internal Docker network only)
- `scheduler` (internal job runner container)
- `database` (MongoDB with persistent volume)

### Access

- Frontend: http://localhost:8080/mail

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
