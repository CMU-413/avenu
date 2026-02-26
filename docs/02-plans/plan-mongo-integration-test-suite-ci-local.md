# Open Questions
None.

# Locked Decisions
- Integration tests run only when `backend/**` changes.
- Integration tests run as a separate `python -m unittest` invocation and are excluded from the unit-test coverage gate.

# Task Checklist
## Phase 1
- ☑ Add a shared Mongo integration-test harness that enforces `DB_NAME=avenu_db_dev`, applies indexes, and drops the test database before each test class.
- ☑ Add integration test A for mail entry persistence against real Mongo-backed repositories.
- ☑ Add integration test B for weekly aggregation correctness using real persisted mail/mailbox/user documents.
- ☑ Add integration test C for notification-log persistence using real `notification_log` writes.

## Phase 2
- ☑ Add a dedicated backend integration-test CI job with a Mongo service container (`mongo:6`) and explicit test DB env (`avenu_db_dev`).
- ☑ Make CI fail when integration tests fail while keeping existing backend unit/coverage checks isolated and intact.

## Phase 3
- ☑ Document a local command path for running only Mongo integration tests with `MONGO_URI` + `DB_NAME=avenu_db_dev`.
- ☑ Add guardrails in docs to avoid production URI/DB usage during integration runs.

## Phase 1: Real-Mongo Integration Test Suite
Affected files and changes
- `backend/tests/integration/__init__.py` (new): mark integration package for deterministic `unittest discover` imports.
- `backend/tests/integration/support.py` (new): centralize Mongo client/test DB setup (`MONGO_URI`, `DB_NAME` assertion, `drop_database`, optional `ensure_indexes`).
- `backend/tests/integration/test_mail_persistence.py` (new): validate insert/read behavior for mail records tied to a real mailbox.
- `backend/tests/integration/test_weekly_aggregation.py` (new): validate `MailSummaryService.getWeeklySummary` over real Mongo documents and week boundaries.
- `backend/tests/integration/test_notification_log_persistence.py` (new): validate real `notification_log` persistence fields for weekly/special-case outcomes.

### Test harness and isolation
- Build one shared base test mixin/class in `support.py` that:
  - reads `MONGO_URI` and `DB_NAME` from env,
  - hard-fails unless `DB_NAME == "avenu_db_dev"`,
  - instantiates a direct `MongoClient` for cleanup,
  - drops `avenu_db_dev` in `setUpClass` only to establish clean module-level state without redundant teardown churn,
  - calls `ensure_indexes()` through the same `config.ensure_indexes()` entrypoint used by application startup so index behavior matches production initialization.
- Keep cleanup value-oriented and centralized; test files should only define fixtures + assertions, not raw cleanup logic.

### Integration test A: mail entry persistence
- Arrange:
  - insert a mailbox via `insert_mailbox(...)` (or direct collection insert if narrower setup is simpler),
  - insert a mail doc via `insert_mail(...)` with deterministic UTC timestamp and count.
- Assert:
  - `list_mail(mailbox_id=...)` returns exactly one persisted entry with expected fields,
  - `find_mail(inserted_id)` returns the same stored fields,
  - a second explicit insert creates a second row (no hidden upsert/overwrite semantics).

### Integration test B: weekly aggregation integrity
- Arrange:
  - insert one user + one mailbox in member scope,
  - insert three mail rows: two `letter` rows inside `[weekStart, weekEnd]`, one `package` row outside range,
  - use deterministic UTC boundaries (fixed `weekStart`/`weekEnd` dates, start-of-week inclusive, end+1-day exclusive) to enforce FR-16 window semantics.
- Execute:
  - call `MailSummaryService().getWeeklySummary(userId=..., weekStart=..., weekEnd=...)`.
- Assert:
  - `totalLetters == 2` and `totalPackages == 0`,
  - mailbox-level `letters/packages` align,
  - daily breakdown includes the full week and excludes out-of-window rows.

### Integration test C: notification-log persistence
- Arrange:
  - call repository/service log writers (`insert_weekly_summary_log` and `insert_special_case_log`, or `insert_notification_log` wrappers) with deterministic payloads.
- Assert against real `notification_log` collection:
  - exactly one row persisted per write operation (QA-R1 single-log-row invariant),
  - correct `type`, `status`, `triggeredBy`, `weekStart`/`templateType` shape,
  - `sentAt` and `errorMessage` semantics preserved for success/failure paths,
  - timestamp fields persisted as datetimes,
  - failure writes remain isolated and append-only (a failed outcome persists its own log row without mutating unrelated records).

## Phase 2: CI Mongo Service + Integration Gate
Affected files and changes
- `.github/workflows/ci-cd.yml`: add a backend integration-test job (or backend-only matrix branch) with `services.mongo` and explicit integration test command/environment.

### CI wiring
- Add job-level service:
  - `mongo` image `mongo:6`,
  - exposed `27017:27017`,
  - optional healthcheck (`mongosh --eval "db.adminCommand('ping')"`) before test execution.
- In integration-test step env, set:
  - `MONGO_URI=mongodb://localhost:27017/avenu_db_dev` (same shape as production URI usage),
  - `DB_NAME=avenu_db_dev` (required by current backend config semantics),
  - `FLASK_TESTING=true` where needed by imports.
- Execute only integration suite path:
  - `python -m unittest discover tests/integration`.
- Keep existing backend unit + coverage step unchanged; run integration as a separate non-coverage job and add `needs`/ordering so PR fails if either backend unit or integration job fails.

### CI scope alignment
- Mirror existing path-filter behavior by running this job only when backend changes.
- Keep Mongo service isolated to CI container network so no Atlas/prod URI is required.

## Phase 3: Local Run Path and Safety Guardrails
Affected files and changes
- `README.md`: add a backend integration test section with exact local command and required env.
- `backend/tests/integration/support.py` (from Phase 1): keep runtime safety checks that refuse non-`avenu_db_dev` DB names.

### Local execution contract
- Document one command shape for local runs:
  - `cd backend && MONGO_URI=mongodb://localhost:27017/avenu_db_dev DB_NAME=avenu_db_dev python -m unittest discover tests/integration`.
- State prerequisite: local Mongo must be reachable on configured URI.
- State failure mode clearly: tests abort if DB name is not `avenu_db_dev`.

### Guardrails
- Enforce explicit DB-name assertion in test harness before any write/drop operation.
- Keep DB cleanup restricted to `avenu_db_dev` only.
- Avoid any fallback to default `avenu_db` during integration runs.
