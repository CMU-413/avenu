# Open Questions
None.

# Locked Decisions
- Convert `backend/models.py` and `backend/repositories.py` into explicit package directories (`backend/models/`, `backend/repositories/`) in this ticket.
- Move `/api/optix-token` into layered `controller -> service -> repository` flow in this ticket with no route contract or behavior changes.
- Enforce transaction/session boundaries strictly in repositories; services must not manage raw Mongo sessions/transactions.
- Add static import-boundary tests in Phase 1 and keep them as CI guardrails for layer-direction violations.

# Task Checklist
## Phase 1
- ☑ Introduce explicit backend layer directories and move HTTP route handlers out of `app.py` into controller blueprints.
- ☑ Move all direct Mongo usage out of service modules into repository modules for user/team/mail/mailbox/member-summary flows.
- ☑ Keep endpoint behavior unchanged while wiring services and repositories through a composition root in `app.py`.
- ☑ Add static import-boundary tests that fail on layer-direction violations (Flask in services, Mongo collections outside repositories, repository bypasses).
- ☑ Ensure transaction/session entrypoints are repository-owned only for all migrated Phase 1 flows.

## Phase 2
- ☑ Refactor mail-request, weekly-summary, and notification paths to strict `Controller -> Service -> Repository -> DB` flow.
- ☑ Ensure scheduler-triggered weekly summary follows documented sequence with no controller/service direct collection access.
- ☑ Move idempotency persistence access behind repositories and keep request replay behavior unchanged.
- ☑ Extend unit tests for weekly summary and mail request flows to validate repository-driven orchestration.

## Phase 3
- ☑ Refactor Optix identity sync into layered flow with repository-owned upsert/data access.
- ☑ Remove remaining cross-layer shortcuts and delete superseded module wiring.
- ☑ Update architecture documentation to state layered backend architecture, dependency direction, and sequence diagram.
- ☑ Confirm docs explicitly preserve existing deployment topology and QA-M1 modifiability constraint.

## Phase 1: Layer Skeleton + Core Route Slice Migration
Affected files and changes
- `backend/app.py`: reduce to composition root only (`create_app`, config/env checks, middleware/error handlers, blueprint registration, dependency wiring); remove route business logic and direct data access.
- `backend/controllers/__init__.py` (new): define blueprint registration entrypoint and request-context wiring.
- `backend/controllers/session_controller.py` (new): move `/api/session/*` handlers, request parsing, response shaping, and auth boundary behavior.
- `backend/controllers/users_controller.py` (new): move `/api/users*` handlers and idempotent create HTTP boundary logic.
- `backend/controllers/teams_controller.py` (new): move `/api/teams*` handlers and `pruneUsers` query parsing/auth checks.
- `backend/controllers/mail_controller.py` (new): move `/api/mail*` handlers and date/mailbox query parsing.
- `backend/controllers/mailboxes_controller.py` (new): move `/api/mailboxes*` handlers.
- `backend/controllers/member_controller.py` (new): move `/api/member/*` handlers and payload/query validation.
- `backend/controllers/auth_guard.py` (new or migrated from `backend/auth.py`): keep Flask session/decorator logic in controller layer only.
- `backend/repositories/__init__.py` (new): repository exports and transaction/session helpers.
- `backend/repositories/mongo.py` (new): centralize Mongo client/collection handle access used by repositories only.
- `backend/repositories/users_repository.py` (new): user CRUD + unique lookups + team membership existence checks.
- `backend/repositories/teams_repository.py` (new): team CRUD + team lookup by internal/external id.
- `backend/repositories/mailboxes_repository.py` (new): mailbox CRUD + member mailbox scope queries.
- `backend/repositories/mail_repository.py` (new): mail entry CRUD + date range list queries.
- `backend/repositories.py` (delete after migration): remove legacy flat repository module once imports are updated.
- `backend/services/user_service.py`: inject/use user/team/mailbox repositories instead of collection imports.
- `backend/services/team_service.py`: inject/use team/user/mailbox/mail repositories with txn boundary kept in repository layer.
- `backend/services/mail_service.py`: replace collection access with mail/mailbox repositories.
- `backend/services/mailbox_service.py`: replace collection access with mailbox repository.
- `backend/services/member_service.py`: replace `users_collection` update with repository call.
- `backend/services/mail_summary_service.py`: consume read repositories for mailbox scope + mail aggregation input.
- `backend/services/mailbox_access_service.py`: move direct query calls into repository functions.
- `backend/models/__init__.py` (new): model exports.
- `backend/models/builders.py` (new, from `backend/models.py`): keep payload-to-domain builders/validators.
- `backend/models/entities.py` (new): define domain entities/typed dicts used across services/repositories.
- `backend/models.py` (delete after migration): remove monolithic model module.
- `backend/tests/test_layered_architecture_boundaries.py` (new): static import-boundary tests (services cannot import Flask; controllers cannot import collections/pymongo; non-repository modules cannot import repository internals that expose raw collections).
- `backend/tests/test_admin_session_auth.py`: update import paths after auth guard move.
- `backend/tests/test_cors_policy.py`: keep passing with `app.py` composition-root rewrite.
- `backend/tests/test_models.py`: repoint tests to `backend/models/builders.py` exports.

Implementation details
- Keep each controller thin: parse request, call service method, convert domain result to JSON.
- Keep DTO/domain conversion (`ObjectId`/datetime serialization) in a dedicated response-mapper utility used by controllers, not services.
- Preserve existing route URLs/status codes/error payloads exactly while moving code.
- Move transaction/session entrypoints (`start_txn`, Mongo session lifecycle) to repository-level utilities and pass repository dependencies into services through constructors/factories from `app.py`.
- Services orchestrate repository calls only and must not start, pass, or depend on raw Mongo sessions/transactions.

Unit tests (phase-local)
- Add `backend/tests/test_layered_architecture_boundaries.py` with:
  - `test_services_do_not_import_flask_request_or_response`
  - `test_controllers_do_not_import_config_collection_handles`
  - `test_non_repository_modules_do_not_import_pymongo_collection_handles`
- Update `backend/tests/test_admin_session_auth.py` for new auth module paths without changing assertions.
- Update `backend/tests/test_models.py` to validate unchanged builder behavior after split into `backend/models/`.

## Phase 2: Weekly Summary + Mail Request Vertical Slice
Affected files and changes
- `backend/controllers/mail_requests_controller.py` (new): move `/api/mail-requests*` and `/api/admin/mail-requests*` request parsing/response mapping.
- `backend/controllers/notifications_controller.py` (new): move admin weekly summary notification endpoint parsing.
- `backend/controllers/internal_jobs_controller.py` (new): move `/api/internal/jobs/weekly-summary` scheduler endpoint, scheduler-token auth check, and idempotency-key extraction.
- `backend/services/mail_request_service.py`: remove direct collection imports, orchestrate mail-request repository + notifier abstraction + notification-log repository.
- `backend/services/notifications/weekly_summary_cron_job.py`: replace direct `users_collection.find` with user repository read method for opted-in users.
- `backend/services/notifications/weekly_summary_notifier.py`: replace user/log collection reads/writes with repository interfaces.
- `backend/services/notifications/special_case_notifier.py`: replace user/log collection reads/writes with repository interfaces.
- `backend/services/notifications/log_repository.py`: migrate into `backend/repositories/notification_logs_repository.py` (new) and keep notifier service decoupled from persistence implementation.
- `backend/services/idempotency_service.py` (new): move idempotency reserve/replay/store orchestration out of controller internals while keeping HTTP-agnostic inputs/outputs.
- `backend/repositories/mail_requests_repository.py` (new): all mail-request CRUD/update/list/filter queries.
- `backend/repositories/notification_logs_repository.py` (new): all notification-log queries/inserts for weekly and special-case notifications.
- `backend/repositories/idempotency_repository.py` (new): idempotency key reserve, replay lookup, response store, and cleanup operations.
- `backend/idempotency.py`: keep hashing/key-validation helpers that are persistence-agnostic; remove direct collection operations.
- `backend/tests/test_mail_request_service.py`: repoint patches to repository dependencies and preserve behavior assertions.
- `backend/tests/test_weekly_summary_scheduler_endpoint.py`: update patch targets to internal jobs controller/service wiring.
- `backend/tests/test_weekly_summary_cron_job.py`: assert opted-in-user list comes from repository adapter.
- `backend/tests/test_weekly_summary_notifier.py`: assert notifier uses repository abstractions for user lookup/logging.
- `backend/tests/test_special_case_notifier.py`: assert notifier uses repository abstractions for user lookup/logging.
- `backend/tests/test_idempotency.py`: repoint to idempotency repository interface while preserving conflict/replay semantics.

Implementation details
- Scheduler flow becomes explicit and layered:
  - Controller authenticates scheduler token and validates payload.
  - Service computes effective week window and orchestrates notifier execution.
  - Repositories handle user selection/idempotency/notification-log persistence.
  - Notification channel abstraction remains a service dependency (no repository or controller calls provider APIs directly).
- Keep retry semantics and side effects identical for:
  - `resolve_mail_request_and_notify`
  - `retry_mail_request_notification`
  - scheduler endpoint idempotency replay.

Unit tests (phase-local)
- Update `backend/tests/test_weekly_summary_scheduler_endpoint.py` with unchanged assertions for token enforcement, single invocation, and replay behavior.
- Update `backend/tests/test_weekly_summary_cron_job.py`:
  - `test_run_weekly_summary_cron_job_fetches_only_opted_in_users` through repository abstraction.
- Update `backend/tests/test_mail_request_service.py` to assert resolve/retry state transitions still happen without direct collection usage.
- Update notifier tests to assert domain behavior is unchanged after repository injection (sent/skipped/failed logging and duplicate-week skip logic).

## Phase 3: External Identity Slice + Documentation Closure
Affected files and changes
- `backend/controllers/identity_controller.py` (new): move `/api/optix-token` route request parsing and HTTP response shaping.
- `backend/services/identity_sync_service.py` (new): implement external identity workflow orchestration (fetch current Optix user, normalize payload, coordinate upsert flows).
- `backend/repositories/users_repository.py`: add user upsert/read methods required for FR-26–29 external identity sync.
- `backend/repositories/teams_repository.py`: add team upsert/read methods required for FR-26–29 external identity sync.
- `backend/services/user_service.py` and `backend/services/team_service.py`: expose/reuse internal create/update primitives needed by identity service without bypassing repositories.
- `backend/tests/test_provider_factory.py` and related identity/session tests: update imports for new identity controller/service boundaries where applicable.
- `docs/architecture/overview.md`: replace “modular backend” wording with explicit layered architecture (5 layers), define dependency direction (`app.py -> controllers -> services -> repositories -> models`), and remove MVC ambiguity.
- `docs/architecture/diagrams/internal-layer-interaction-sequence.mmd` (new): add sequence diagram for required backend interaction flow (Frontend and Scheduler paths).
- `docs/deployment.md`: add explicit confirmation that deployment topology remains unchanged (frontend/backend/scheduler/database containers and network paths).
- `docs/03-quality-attributes.md`: add explicit confirmation that QA-M1 remains satisfied after layering by keeping provider swaps isolated from persistence/domain logic.

Implementation details
- Keep all external provider calls in service-layer integrations; controllers and repositories stay provider-agnostic.
- Ensure identity sync upsert logic (teams/users) is repository-owned and called only via service orchestration.
- Remove any remaining legacy imports that violate layer direction after identity route migration.

Unit tests (phase-local)
- Add `backend/tests/test_identity_sync_service.py` (new):
  - create-new-user/team path
  - existing-user update path
  - Optix failure path preserves local state
- Add `backend/tests/test_identity_controller.py` (new):
  - missing token validation
  - provider failure passthrough status handling
  - created vs updated response contract
- Keep documentation-only changes untested in code; no integration/manual test steps added.
