# Avenu

Full-stack web application composed of:

* React SPA (frontend)
* Flask API (backend)
* Dedicated Scheduler container (job runner)
* MongoDB database

Docker is the source of truth for local, CI, and production environments.

---

## System Overview

* Frontend is a pure API client.
* Backend owns all business logic and all database access.
* Scheduler is an internal backend client that triggers scheduled jobs.
* Scheduler never connects directly to MongoDB.
* All inter-service traffic runs inside the Docker network.
* External traffic only reaches the frontend (and backend if exposed).

---

## Repo Structure

```
├── frontend/        # React SPA
├── backend/         # Flask API + business logic
├── scheduler/       # Scheduled job runner (backend client)
├── docs/            # Architecture and API docs
├── docker-compose.yml
└── README.md
```

---

## Prerequisites

Required:

* Docker (with Docker Compose v2)

Optional (for running outside Docker):

* Node.js
* Python 3.11+

---

## Environment Configuration

Copy:

```
.env.sample → .env
```

### Backend

* `SECRET_KEY` (required outside tests)
* `FLASK_TESTING`
* `FRONTEND_ORIGINS` (CORS allowlist)
* `SCHEDULER_INTERNAL_TOKEN` (shared secret for scheduler endpoint)
* `AUTH_MAGIC_LINK_BASE_URL` (public SPA entry used in emailed sign-in links)
* `AUTH_MAGIC_LINK_PATH` (verification route or query-bearing SPA path, default `/`)
* `AUTH_MAGIC_LINK_EXPIRY_SECONDS` (magic-link lifetime in seconds, default `900`)
* optional: `AUTH_MAGIC_LINK_SECRET` (falls back to `SECRET_KEY`)

### Notification Providers (required when `FLASK_TESTING=false`)

* `MS_GRAPH_TENANT_ID`
* `MS_GRAPH_CLIENT_ID`
* `MS_GRAPH_CLIENT_SECRET`
* `MS_GRAPH_SENDER_EMAIL`
* `TWILIO_ACCOUNT_SID`
* `TWILIO_AUTH_TOKEN`
* `TWILIO_PHONE_NUMBER`

### Session / Embedding

For iframe / Canvas embedding:

* `SESSION_COOKIE_NAME=avenu_session`
* `SESSION_COOKIE_SAMESITE=Lax` for same-site flows, or `None` for iframe embedding
* `SESSION_COOKIE_SECURE=true`
* optional: `SESSION_COOKIE_PARTITIONED=true`

### Frontend (Build-Time)

* `VITE_BASE_PATH` (default `/mail/`)
* `VITE_API_BASE_URL` (default `/mail/api`)

These are public and embedded at build time.

### Scheduler

* `BACKEND_API_URL` (default `http://backend:8000`)
* `SCHEDULER_INTERNAL_TOKEN`
* `SCHEDULER_CRON` (default `0 8 * * 1`)
* `SCHEDULER_TIMEZONE`
* `SCHEDULER_TICK_SECONDS`

---

## Authentication Model

Production usage assumes authentication is handled upstream (e.g., Optix or embedding context).

The backend now includes configuration for admin magic-link authentication:

* `AUTH_MAGIC_LINK_BASE_URL` should point at the public SPA mount, for example:
  * local: `http://localhost:8080/mail`
  * production: `https://hub.avenuworkspaces.com/mail`
* `AUTH_MAGIC_LINK_PATH` should remain aligned with the frontend/nginx entry behavior so callback query params survive the `/mail` to `/mail/` normalization.

The existing public email-post login flow is being replaced by magic-link request/redeem endpoints and should not be treated as the long-term public auth contract.

---

## Running the App (Docker)

From repo root:

```
docker compose up --build
```

Services:

* frontend → [http://localhost:8080/mail](http://localhost:8080/mail)
* backend → internal
* scheduler → internal
* database → MongoDB (persistent volume)

---

## Running Without Docker

### Backend

```
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
python3 app.py
```

Runs on: [http://localhost:8000](http://localhost:8000)

### Backend Mongo Integration Tests

Prerequisite: a local Mongo instance is reachable at `localhost:27017`.

```
cd backend
RUN_MONGO_INTEGRATION=1 MONGO_URI=mongodb://localhost:27017/avenu_db_dev DB_NAME=avenu_db_dev python -m unittest discover tests/integration
```

Safety guardrails:

* Integration tests only run when `RUN_MONGO_INTEGRATION=1`.
* Integration tests require `DB_NAME=avenu_db_dev` and will fail fast for any other DB name.
* The test harness drops only `avenu_db_dev`; no fallback to `avenu_db`.

### Admin OCR Smoke Test

Exercises the full admin OCR flow end-to-end — bulk upload, background worker,
review, confirm, idempotent retry, soft-delete, and stage transitions — against
a live Mongo using the real Tesseract provider.

Prerequisites: `tesseract-ocr` installed (`apt install tesseract-ocr`), backend
venv active, and a reachable `mongod`.

```
cd backend
MONGO_URI=mongodb://127.0.0.1:27017 DB_NAME=optix_smoke \
    python scripts/smoke_ocr_flow.py
```

Drops and re-creates `optix_smoke`; safe to re-run. Exits non-zero on any
regression and logs every observed state transition.

### Frontend

```
cd frontend
npm install
npm run dev
```

Runs on: [http://localhost:8080/mail](http://localhost:8080/mail)

Local Vite dev uses the same `/mail` base path as Docker.

API requests to `/mail/api/*` are proxied to the backend at `http://localhost:8000/api/*`.

### Scheduler

```
cd scheduler
SCHEDULER_INTERNAL_TOKEN=<token> BACKEND_API_URL=http://localhost:8000 python main.py
```

---

## CI / Docker Hub

GitHub Actions builds and pushes:

* `DOCKERHUB_USERNAME/avenu-frontend`
* `DOCKERHUB_USERNAME/avenu-backend`
* `DOCKERHUB_USERNAME/avenu-scheduler`

Required repo secrets:

* `DOCKERHUB_USERNAME`
* `DOCKERHUB_TOKEN`

Deployment targets must pull images from the same Docker Hub namespace.

---

## Notes

* Frontend environment variables are build-time and public.
* Backend environment variables are runtime and private.
* Scheduler is an internal API client.
* Docker is the canonical deployment path.
