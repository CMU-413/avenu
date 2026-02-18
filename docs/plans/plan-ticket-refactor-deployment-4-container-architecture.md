# Open Questions
None.

# Locked Decisions
- Scheduler cadence is runtime-configurable via `SCHEDULER_CRON` and `SCHEDULER_TIMEZONE`, defaulting to `0 8 * * 1` in `UTC`.
- Scheduler triggers use a dedicated internal endpoint: `POST /api/internal/jobs/weekly-summary`.
- Scheduler endpoint auth uses shared secret header `X-Scheduler-Token`, and calls include deterministic idempotency keys.
- Scheduler runs its own internal cron loop (no host-level cron dependency).
- `docker-compose.yml` sets `scheduler` restart policy to `unless-stopped`.
- `docker-compose.yml` includes healthchecks for `backend` and `database`.
- Scheduler internal endpoint is excluded from public API documentation.

# Task Checklist
## Phase 1
- ☑ Remove monolithic runtime artifacts (`root Dockerfile`, root `nginx.conf`, `start.sh`) and define one container per responsibility.
- ☑ Normalize Backend runtime to port `8000` and keep DB/external integrations exclusively in Backend.
- ☑ Rework frontend runtime to static SPA serving only (no `/api` reverse-proxy behavior).
- ☑ Add a dedicated Scheduler container image that only calls Backend over HTTP and does not install DB dependencies.
- ☑ Replace compose topology with `frontend`, `backend`, `scheduler`, and `database` services on a shared internal network plus Mongo volume.
- ☑ Configure Scheduler service with `restart: unless-stopped` and wire compose healthchecks for Backend and Database.

## Phase 2
- ☑ Add a scheduler-only Backend HTTP endpoint to trigger weekly summary jobs and keep Scheduler as an API client only.
- ☑ Add job-trigger idempotency at the API boundary so restart/retry does not duplicate weekly sends.
- ☑ Add explicit CORS origin allowlist config for frontend origin(s), with no wildcard production policy.
- ☑ Move service configuration/secrets entirely to env contracts for frontend, backend, and scheduler.
- ☑ Add unit tests for scheduler request formation/idempotency and backend endpoint/CORS behavior.
- ☑ Implement scheduler internal cron loop using `SCHEDULER_CRON`/`SCHEDULER_TIMEZONE` defaults (`0 8 * * 1`, `UTC`).

## Phase 3
- ☐ Update architecture docs and README deployment guidance to match the 4-container runtime exactly.
- ☐ Remove all legacy references to single app container, embedded scheduler, and internal reverse proxy routing.
- ☐ Document service boundaries, Docker DNS names, and allowed communication paths explicitly.
- ☐ Keep scheduler internal endpoint out of public API contract docs.

## Phase 1: Container Boundary Refactor + Compose Topology
Affected files and changes
- `Dockerfile`: remove monolithic multi-process image (frontend + nginx + backend) from active deployment path.
- `nginx.conf`: remove internal `/api` proxy config from root runtime artifact.
- `start.sh`: remove process-supervisor script that boots Flask + nginx in one container.
- `backend/Dockerfile`: update runtime contract to serve Flask API on `0.0.0.0:8000`; keep only backend code/dependencies.
- `frontend/Dockerfile`: keep build + static serving, but remove any API-proxy coupling; frontend is static assets only.
- `frontend/nginx.conf` (new): SPA static-file config only (`try_files` fallback), no `/api` upstreams.
- `scheduler/Dockerfile` (new): create dedicated Scheduler image with lightweight Python runtime and HTTP client deps only.
- `scheduler/` package (new): add scheduler entrypoint (`main.py`) that triggers backend weekly job endpoint over HTTP.
- `docker-compose.yml`: replace `app` service with `frontend`, `backend`, `scheduler`, `database`; add explicit network, service DNS, `depends_on`, and Mongo named volume.
- `docker-compose.yml`: set `scheduler.restart: unless-stopped` and add healthchecks for `backend` and `database`, with scheduler depending on healthy backend.
- `.dockerignore`: update ignore rules for new service folders/build contexts if needed.

Implementation details
- Backend becomes the only service with database/external-provider libraries and credentials.
- Scheduler service gets only scheduler/job-trigger code and backend URL config (`BACKEND_API_URL=http://backend:8000`).
- Frontend service receives API base URL env at build/runtime contract (`VITE_API_BASE_URL`/`API_BASE_URL`), and calls Backend directly over Docker network boundary.
- Compose service names become authoritative DNS endpoints inside network (`backend`, `database`, `frontend`, `scheduler`).
- No internal reverse proxy inside app containers; each container runs a single concern.

Unit tests (phase-local)
- No new unit tests in this phase for pure container/declarative compose changes.
- Keep logic-heavy tests in Phase 2 where new scheduler + backend boundary logic is introduced.

## Phase 2: Scheduler-to-Backend API Contract, Idempotency, and CORS
Affected files and changes
- `backend/app.py`: add scheduler-trigger endpoint `POST /api/internal/jobs/weekly-summary` that executes the weekly job via existing job runner/notifier wiring.
- `backend/app.py`: add CORS policy wiring driven by env allowlist (frontend origin list), denying wildcard in non-testing mode.
- `backend/config.py`: add typed env accessors for `FRONTEND_ORIGINS`, scheduler auth secret, and backend URL/port runtime settings.
- `backend/idempotency.py` and/or `backend/app.py`: reuse existing idempotency-key mechanism on scheduler endpoint with deterministic key (`weekly-summary:<weekStart>`), returning replayed response for duplicates.
- `backend/scripts/run_weekly_summary_cron.py`: keep command path for local/manual use, but make it reuse the same backend job function used by the new endpoint.
- `scheduler/main.py` (new): run internal cron loop, compute current target week trigger payload, send HTTP request to backend endpoint, include scheduler auth + idempotency key, and log structured outcomes.
- `scheduler/client.py` (new): isolated backend HTTP client wrapper to keep scheduler loop declarative and testable.
- `scheduler/config.py` (new): typed env parsing for `BACKEND_API_URL`, schedule expression, timezone, and auth token.
- `backend/tests/test_weekly_summary_scheduler_endpoint.py` (new): endpoint behavior coverage.
- `backend/tests/test_cors_policy.py` (new): CORS configuration coverage.
- `scheduler/tests/test_backend_client.py` (new): scheduler request/idempotency behavior coverage.

Implementation details
- Scheduler is strictly a backend client:
  - No imports from backend business modules.
  - No `pymongo` in scheduler dependencies.
  - All job actions happen through Backend HTTP API.
- Scheduler execution model:
  - Internal cron loop in scheduler container (no host cron).
  - Cadence/timezone from `SCHEDULER_CRON` and `SCHEDULER_TIMEZONE` with defaults `0 8 * * 1` and `UTC`.
- Add scheduler endpoint auth via shared secret header (e.g. `X-Scheduler-Token`) sourced from env to prevent public invocation.
- API-level idempotency:
  - Scheduler sends deterministic idempotency key per weekly window.
  - Backend reuses idempotency storage so restart/retry returns replay result instead of re-dispatching work.
- CORS:
  - Parse explicit allowed origins from env.
  - Allow credentials and required methods/headers only.
  - Fail fast on wildcard origin in non-testing configuration.

Unit tests (phase-local)
- `backend/tests/test_weekly_summary_scheduler_endpoint.py`:
  - `test_scheduler_endpoint_requires_scheduler_token`
  - `test_scheduler_endpoint_invokes_weekly_job_runner_once`
  - `test_scheduler_endpoint_replays_response_when_idempotency_key_reused`
- `backend/tests/test_cors_policy.py`:
  - `test_cors_allows_configured_frontend_origin`
  - `test_cors_blocks_unconfigured_origin`
  - `test_cors_rejects_wildcard_origin_in_non_testing_mode`
- `scheduler/tests/test_backend_client.py`:
  - `test_client_posts_to_backend_service_url`
  - `test_client_sends_scheduler_auth_and_idempotency_headers`
  - `test_client_treats_replayed_response_as_success`
  - `test_client_handles_non_2xx_with_structured_error`

## Phase 3: Documentation Realignment to Runtime Topology
Affected files and changes
- `docs/architecture/diagrams/container-diagram.mmd`: confirm this remains the canonical deployment diagram and matches compose/service names.
- `docs/architecture/overview.md`: rewrite deployment topology sections from single `app` container to four-container model.
- `docs/architecture/notification-system.md`: update scheduler execution narrative to “Scheduler container -> Backend API”, not in-process backend scheduling.
- `README.md`: replace deployment/run instructions with four-service compose flow, service ports, env contracts, and DNS communication model.
- `.env.sample`: include complete, non-secret placeholders for backend/frontend/scheduler env variables and remove stale assumptions.
- `docs/api/member-api-contract.md` and `docs/api/admin-notification-api-contract.md`: keep public/member/admin API docs free of scheduler-internal endpoint references.
- `docs/02-technical-constraints.md` and `docs/03-quality-attributes.md` (if references exist): align constraints/scenarios with separated scheduler container and backend-only DB ownership.

Implementation details
- Remove legacy references to:
  - single combined application container,
  - internal nginx reverse proxy between frontend/backend,
  - scheduler embedded inside backend runtime.
- Add explicit communication matrix in docs:
  - Frontend -> Backend (HTTP)
  - Scheduler -> Backend (HTTP)
  - Backend -> Database
  - Backend -> Optix / Email Provider / OCR Provider
- Clarify logical architecture vs deployment architecture in overview documentation.

Unit tests (phase-local)
- No code-path unit tests expected for documentation-only changes.
