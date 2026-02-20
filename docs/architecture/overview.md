# Architecture Overview

## 1. Architectural Style

Avenu uses a modular backend with a four-container deployment topology:

- Frontend container (React SPA)
- Backend container (Flask API)
- Scheduler container (time-based job runner)
- Database container (MongoDB)

This architecture keeps service responsibilities separate while preserving a single backend business-logic boundary.

## 2. Deployment Topology

### 2.1 Frontend (`frontend`)

- Serves static React SPA assets.
- Used by members and admins.
- Calls Backend HTTP API only.
- Does not access MongoDB or external providers directly.

### 2.2 Backend (`backend`)

- Hosts all API routes and business logic.
- Owns persistence and data access to MongoDB.
- Owns all external integrations (Optix, Email Provider, OCR Provider).
- Exposes HTTP API on port `8000`.

### 2.3 Scheduler (`scheduler`)

- Runs independent schedule loop via `SCHEDULER_CRON` and `SCHEDULER_TIMEZONE`.
- Triggers weekly-summary job through backend internal endpoint:
  - `POST /api/internal/jobs/weekly-summary`
- Uses shared secret header (`X-Scheduler-Token`) and idempotency key.
- Does not access MongoDB directly.

### 2.4 Database (`database`)

- MongoDB with persistent volume.
- Stores users, teams, mailboxes, mail entries, and notification preferences.
- Accessible only to Backend in application architecture.

## 3. Communication Boundaries

Allowed communication paths:

- Frontend -> Backend (HTTP)
- Scheduler -> Backend (HTTP)
- Backend -> Database
- Backend -> Optix
- Backend -> Email Provider
- Backend -> OCR Provider

Disallowed paths:

- Frontend -> Database
- Scheduler -> Database
- Frontend -> External providers
- Scheduler -> External providers

## 4. Internal Docker DNS Model

Within the compose network, service DNS names are:

- `frontend`
- `backend`
- `scheduler`
- `database`

Scheduler reaches backend at `http://backend:8000`.

## 5. Logical vs Deployment Architecture

Logical architecture:

- Backend modules for identity, mailbox management, mail logging, aggregation, and notifications.

Deployment architecture:

- Those backend modules all run in the single Backend container.
- Frontend and Scheduler run as separate containers that consume backend APIs.

## 6. Scheduling Model

- Weekly summary execution is initiated by Scheduler container.
- Backend executes the job and handles notification dispatch.
- API-level idempotency prevents duplicate execution on retries/restarts.

## 7. Design Constraints

- No combined monolithic application container.
- No internal reverse-proxy routing inside application containers.
- Inter-service app communication uses explicit HTTP boundaries.
- Secrets/configuration come from environment variables, not image-embedded values.

## 8. Frontend API Layering

Frontend API access is organized as a layered route architecture:

- `frontend/src/lib/http/client.ts`:
  - Transport boundary only (`API_BASE_URL`, `buildUrl`, `apiFetch`).
  - Owns fetch defaults and HTTP error parsing.
- `frontend/src/lib/http/errors.ts`:
  - Shared `ApiError` type for HTTP failures.
- `frontend/src/lib/api/contracts/types.ts`:
  - API transport contracts (`Api*` request/response types and unions).
  - No executable request logic.
- `frontend/src/lib/api/routes/*`:
  - Route wrapper layer grouped by backend route prefixes (session, mail, users, teams, member, admin mail requests, notifications, optix).
  - Thin wrappers that call `apiFetch` and return typed responses.
- `frontend/src/lib/api/index.ts`:
  - UI consumption boundary.
  - Re-exports contracts and route wrappers as the public frontend API surface.
