# Open Questions
- None.

# Locked Decisions
- HTTP boundary tests use the Flask app factory (`create_app(testing=True, ensure_db_indexes_on_startup=False)`), real repositories, and real Mongo test DB (`avenu_db_dev`).
- HTTP boundary tests stay in `backend/tests/integration/` and run under the existing `RUN_MONGO_INTEGRATION=1` guard (no additional flag).
- HTTP integration remains part of Mongo-backed integration coverage, but runs in a dedicated CI job `backend-http-integration` for clearer failure isolation.
- Controller/service/repository wiring is exercised via real HTTP requests; services, repositories, and controllers are not mocked.
- External transport behavior is the only mocked seam (patch provider `send()` methods in tests); no new provider-specific test hooks are introduced unless implementation proves strictly necessary.
- Authorization invariants are asserted at HTTP response and persistence levels (403/401 + no unauthorized mutation).
- The scheduler contract is tested through `POST /api/internal/jobs/weekly-summary` with scheduler-token enforcement and per-recipient failure isolation.

# Task Checklist
## Phase 1
- ☑ Add a reusable HTTP integration test harness (app client + DB cleanup + fixture helpers) on top of the existing Mongo integration support.
- ☑ Add authentication/authorization HTTP integration tests for 401, cross-mailbox 403, and mutation non-occurrence.

## Phase 2
- ☑ Add a mail logging -> member dashboard aggregation integration test using real HTTP endpoints and persisted records.
- ☑ Add weekly-summary internal-job integration tests for scheduler token enforcement, continue-on-failure semantics, idempotency replay, and notification-log persistence.

## Phase 3
- ☑ Wire the HTTP integration suite into CI as a required backend check.
- ☑ Update architecture/testing documentation to include HTTP boundary integration coverage and the protected guarantees.

## Phase 1: HTTP Harness + AuthZ Boundary Coverage
Affected files and changes
- `backend/tests/integration/support.py`: extend support utilities with an HTTP-focused base case that creates a Flask test client, provides deterministic DB reset per test, and shared fixture builders (`insert_user`, `insert_mailbox`, `insert_mail_request` helpers).
- `backend/tests/integration/test_http_authz_boundary.py` (new): add controller-to-repository authorization integration coverage via real HTTP calls.
- `backend/tests/integration/__init__.py`: keep package discovery stable for added HTTP tests.

### Harness changes
- Add a `HttpIntegrationTestCase` that composes current Mongo safety checks with:
  - `create_app(testing=True, ensure_db_indexes_on_startup=False, secret_key="test-secret")`
  - `self.client = app.test_client()`
  - deterministic per-test collection cleanup for `mail`, `mail_request`, `notification_log`, `idempotency_keys`, `mailbox`, `users`, `teams`.
- Add helper methods to seed admin/member users and mailbox ownership so tests avoid hand-rolled fixtures.

### HTTP authorization tests
- `test_protected_endpoint_requires_authentication`
  - Call protected routes (for example `GET /api/member/mail`, `GET /api/users`) without session; assert `401`.
- `test_member_cross_mailbox_mutation_is_forbidden_and_no_write_occurs`
  - Seed member A, member B, and mailbox owned by B.
  - Log in as member A via `POST /api/session/login`.
  - Attempt `POST /api/mail-requests` with B mailbox ID; assert `403`.
  - Assert `mail_request` collection has no row for attempted payload/member.
- `test_member_admin_boundary_rejects_admin_for_member_route`
  - Seed admin user, log in, call `GET /api/member/mail`; assert `403`.

## Phase 2: Aggregation and Internal Job Contract Coverage
Affected files and changes
- `backend/tests/integration/test_http_mail_dashboard_consistency.py` (new): add admin-mail-create and member-dashboard-read consistency assertions.
- `backend/tests/integration/test_http_weekly_summary_job.py` (new): add internal-job HTTP contract tests, including token enforcement and failure isolation.

### Mail logging -> dashboard consistency test
- Seed admin user, member user, and member mailbox in real DB.
- As admin session, call `POST /api/mail` twice (letter/package rows inside target week).
- As member session, call `GET /api/member/mail?start=...&end=...`.
- Call `MailSummaryService().getWeeklySummary(...)` for the same member and week window.
- Assert dashboard response totals and per-day mailbox counts match both persisted rows and weekly-summary totals (FR-9, FR-10, FR-15, FR-16, FR-17, QA-R3).

### Weekly summary internal-job integration tests
- `test_internal_weekly_summary_requires_scheduler_token`
  - Call `POST /api/internal/jobs/weekly-summary` without `X-Scheduler-Token`; assert `401`.
- `test_internal_weekly_summary_continues_when_one_recipient_transport_fails`
  - Seed two opted-in users with non-empty weekly summaries.
  - Patch only provider transport `send()` behavior: fail for one recipient, succeed for another.
  - Call internal job endpoint with valid scheduler token and idempotency key.
  - Assert HTTP 200 response counters reflect continued processing (`processed == 2`, `errors/failed` non-zero, at least one success).
  - Assert `notification_log` has one row per attempted recipient and includes failure row with `type="weekly-summary"` and `status="failed"` (FR-24, FR-35, QA-R1).
- `test_internal_weekly_summary_replays_on_reused_idempotency_key`
  - Call the endpoint twice with identical `Idempotency-Key` + payload.
  - Assert same response body/status is replayed and underlying execution side effects (notification-log growth) occur only once.

## Phase 3: CI Gate + Documentation Alignment
Affected files and changes
- `.github/workflows/ci-cd.yml`: add a dedicated `backend-http-integration` job that runs HTTP integration tests in CI with required Mongo-backed environment; fail pipeline on any invariant break.
- `docs/00-drivers/04-quality-assurance.md`: update test-layer section to include HTTP boundary integration tests and the specific invariants covered (`QA-S1`, `QA-R1`, `QA-R3`).
- `docs/01-architecture/notification-system.md`: add/adjust coverage note that scheduler trigger path `POST /api/internal/jobs/weekly-summary` is integration-tested at HTTP boundary.
- `docs/01-architecture/overview.md`: add a short coverage note that mailbox authorization and internal weekly-summary endpoint are covered by automated HTTP integration tests.

### CI wiring
- Keep unit tests/coverage job unchanged.
- Keep existing Mongo repository integration job unchanged.
- Add dedicated `backend-http-integration` invocation, for example:
  - `python -m unittest discover -s tests/integration -p "test_http_*.py" -t .`
- Preserve explicit env guardrails:
  - `RUN_MONGO_INTEGRATION=1`
  - `MONGO_URI=mongodb://localhost:27017/avenu_db_dev`
  - `DB_NAME=avenu_db_dev`
  - `FLASK_TESTING=true`
- Ensure this job is required for backend changes and blocks deploy on failure.
