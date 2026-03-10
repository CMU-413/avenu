# Open Questions
None.

# Locked Decisions
- Health status contract is provider-agnostic and value-based: each dependency returns one of `healthy`, `unreachable`, `misconfigured`, `error`.
- `/api/health` is process liveness only and does not touch external systems.
- `/api/health/dependencies` is side-effect free and bounded by short per-provider timeouts plus a hard total deadline.
- Dependency checks are isolated and aggregated; one failing dependency never short-circuits others.
- Legacy `/health` is removed; only `/api/health` and `/api/health/dependencies` are supported.
- OCR is out of scope for this ticket and omitted from the dependency map until an OCR provider abstraction exists.
- Health coverage is unit-test only for this ticket; no additional integration tests are added.
- Dependency response shape is deterministic with stable keys (`mongo`, `graph`, `twilio`) and always returns the full map, including failure responses.

# Task Checklist
## Phase 1
- ☑ Add a dedicated `HealthService` with composable dependency check adapters and normalized status mapping (`healthy`/`unreachable`/`misconfigured`/`error`).
- ☑ Reuse existing dependency clients (Mongo config client, Optix HTTP call path, MS Graph provider token path, Twilio client path) without duplicating business logic.
- ☑ Add unit tests for status normalization, timeout handling, and per-provider isolation.

## Phase 2
- ☑ Add `GET /api/health` returning `200` with `{ "status": "ok" }` only.
- ☑ Add `GET /api/health/dependencies` returning aggregated dependency statuses and `503` when any dependency is non-healthy.
- ☑ Ensure endpoint behavior is deterministic and side-effect free under dependency failures.

## Phase 3
- ☑ Update/replace existing health route tests (`/health`) to cover `/api/health` and `/api/health/dependencies` contracts.
- ☑ Add HTTP-level backend unit tests for full response shape and status-code behavior across all-healthy and partial-failure scenarios.
- ☑ Keep this ticket unit-only: no new integration tests.

## Phase 1: HealthService + Dependency Adapters
Affected files and changes
- `backend/services/health_service.py` (new): define `HealthService` with `check_dependencies() -> dict[str, str]`, plus provider-check methods for `mongo`, `graph`, and `twilio`.
- `backend/services/__init__.py`: export `HealthService` for controller/app usage.
- `backend/services/notifications/providers/ms_graph_provider.py`: add a side-effect-free health probe entrypoint (for example `check_health(timeout_seconds: float) -> str`) that reuses existing token acquisition flow.
- `backend/services/notifications/providers/twilio_sms_provider.py`: add a side-effect-free health probe entrypoint using Twilio account fetch/read-only validation (no message send).

### Service design
- Implement `HealthService` as a thin orchestrator with:
  - explicit dependency list and stable response keys,
  - per-provider timeout budget (`<=1s`) and overall deadline (`<=3s`),
  - exception-to-status mapping rules:
    - timeout/network failures -> `unreachable`,
    - auth/config errors -> `misconfigured`,
    - unexpected exceptions -> `error`.
- Keep check execution independent by wrapping each check in its own exception boundary and storing results as immutable values in the response map.
- Mongo check uses read-only ping (`client.admin.command("ping")`) with short server selection timeout; no writes, inserts, or queue interactions.
- Graph/Twilio checks use safe auth/identity paths only; no sends, no mutation endpoints.
- If total deadline is reached mid-evaluation, assign remaining dependencies `unreachable` so the endpoint returns promptly with the full stable map.

### Unit tests (phase-local)
- `backend/tests/unit/test_health_service.py` (new):
  - returns all dependency keys with `healthy` when each adapter reports success,
  - maps timeout-like failures to `unreachable`,
  - maps explicit auth/config exceptions to `misconfigured`,
  - maps unknown exceptions to `error`,
  - preserves isolation (one adapter raising does not block remaining adapters),
  - enforces total runtime guard with mocked slow adapters.

## Phase 2: Health Endpoints + HTTP Status Behavior
Affected files and changes
- `backend/controllers/health_controller.py` (new): expose `GET /api/health` and `GET /api/health/dependencies`.
- `backend/controllers/__init__.py`: register `health_bp`.
- `backend/app.py`: remove inline `/health` route and keep controller-driven `/api` health surface.

### Endpoint behavior
- `GET /api/health`:
  - always returns `200` and `{ "status": "ok" }`,
  - performs no dependency checks.
- `GET /api/health/dependencies`:
  - obtains `statuses = HealthService().check_dependencies()`,
  - returns `200` only when all values are `healthy`,
  - returns `503` when any value is `unreachable`, `misconfigured`, or `error`,
  - always returns the full stable JSON map with keys in deterministic order: `mongo`, `graph`, `twilio`.

### Unit tests (phase-local)
- `backend/tests/unit/test_health_controller.py` (new):
  - `/api/health` returns `200` with exact JSON body,
  - `/api/health/dependencies` returns `200` when mocked service is all `healthy`,
  - `/api/health/dependencies` returns `503` when any dependency is non-healthy,
  - verifies contract uses only allowed status literals.

## Phase 3: Test Realignment + CI-Safe Coverage
Affected files and changes
- `backend/tests/unit/test_cors_policy.py`: switch probes from `/health` to `/api/health` so CORS checks continue validating allowed/disallowed origins on a live route.
- `backend/tests/unit/test_health_controller.py` and `backend/tests/unit/test_health_service.py`: finalize edge-case assertions for partial failure payloads and stable key presence.

### Test updates
- Replace assumptions tied to legacy `/health` response shape (`{"message":"HEALTH OK"}`) with the new liveness contract (`{"status":"ok"}`).
- Keep health endpoint tests deterministic by mocking external providers in unit scope.
- Add explicit unit assertions that `503` responses still include all dependency keys with valid status literals.
