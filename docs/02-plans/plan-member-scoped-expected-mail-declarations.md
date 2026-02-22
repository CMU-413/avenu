# Open Questions
- None.

# Locked Decisions
- Add a dedicated `mail_requests` Mongo collection and keep `memberId` as internal user reference (`users._id`, `ObjectId`) derived from authenticated session user only.
- Store lifecycle with `status` enum string values only: `ACTIVE`, `CANCELLED`; cancellation is a soft delete (`$set` status + `updatedAt`).
- Keep declaration layer isolated: no linkage with `mail`, no scheduler/notification hooks, no aggregation changes.
- Reuse mailbox ownership rules via a shared mailbox-access helper (member personal mailbox + team mailboxes) instead of duplicating mailbox query logic across features.
- Member API returns only ACTIVE own records, sorted `createdAt DESC`; admin API returns only ACTIVE records with optional `mailboxId` + `memberId` filters.
- Use API-only routes for this feature: `/api/mail-requests` and `/api/admin/mail-requests` (no alias routes).
- `DELETE /api/mail-requests/{id}` returns `404` unless a record matches `{ _id, memberId, status: "ACTIVE" }`; implement cancellation as a single atomic update.
- Admin `memberId` filter must be an ObjectId string; invalid format returns `422`.

# Task Checklist
## Phase 1
- ☑ Add `MAIL_REQUEST` persistence model, validation builders, and indexes.
- ☑ Introduce shared member mailbox-access helper and `mail_request_service` for create/list/cancel/admin-list flows.
- ☑ Add backend route handlers for member create/list/cancel and admin active-list with filter parsing + auth enforcement.
- ☑ Add backend unit tests for validation, authorization boundaries, scoping, sorting, and soft-delete behavior.

## Phase 2
- ☑ Extend frontend API typings/helpers for member/admin mail-request endpoints.
- ☑ Add member dashboard “Expected Mail” section with create/list/cancel UX and mailbox-scoped selection.
- ☑ Add admin read-only active-request table view with optional member/mailbox filtering.
- ☑ Add focused frontend unit tests for form validation and API wiring on member/admin mail-request UI flows.

## Phase 3
- ☑ Update architecture data model docs with `MAIL_REQUEST` entity, fields, and lifecycle state semantics.
- ☑ Update API docs with new member/admin mail-request endpoints, request/response schemas, and authorization behavior.

## Phase 1: Backend Domain + Auth-Scoped API
Affected files and changes
- `backend/config.py`: add `mail_requests_collection = db["mail_requests"]`; extend `ensure_indexes()` with:
  - `("memberId", ASCENDING), ("status", ASCENDING)`
  - `("mailboxId", ASCENDING), ("status", ASCENDING)`
  - `("status", ASCENDING)`
- `backend/models.py`: add `MAIL_REQUEST_STATUSES`; add `build_mail_request_create(payload, *, member_id: ObjectId)` enforcing:
  - valid `mailboxId` ObjectId string
  - at least one non-empty `expectedSender` or `description`
  - optional ISO `startDate`/`endDate` parse and `endDate >= startDate`
  - immutable `memberId` (ObjectId) from auth context
  - initialized `status="ACTIVE"`, timestamps
- `backend/services/mailbox_access_service.py` (new): extract composable mailbox scope helpers:
  - `member_mailbox_scope(user)` query builder (user mailbox + team mailboxes)
  - `assert_member_mailbox_access(user, mailbox_id)` that raises `APIError(403, "forbidden")` on unauthorized mailbox access
  - `list_member_mailboxes(user)` utility for member-owned mailbox docs (reused by summary + request logic)
- `backend/services/mail_summary_service.py`: replace inline mailbox `$or` construction with `member_mailbox_scope(...)` helper to de-complect mailbox access logic and keep one source of truth.
- `backend/services/mail_request_service.py` (new): implement declaration workflows:
  - `create_mail_request(user, payload)` validates + checks mailbox access + inserts
  - `list_member_active_mail_requests(user)` query by `memberId=user["_id"]` + `status="ACTIVE"` sorted by `createdAt DESC`
  - `cancel_member_mail_request(user, request_id)` performs one atomic guarded update on `{_id, memberId, status:"ACTIVE"}` and returns `404` when unmatched
  - `list_admin_active_mail_requests(mailbox_id=None, member_id=None)` for active read-only admin view
- `backend/repositories.py`: include `mail_requests_collection` import and keep shared `to_api_doc` serialization path for datetime/ObjectId conversion.
- `backend/app.py`: add routes:
  - `POST /api/mail-requests` (member-only, body validation delegated to service, 201)
  - `GET /api/mail-requests` (member-only, ACTIVE own records)
  - `DELETE /api/mail-requests/<id>` (member-only, soft-cancel own record)
  - `GET /api/admin/mail-requests` (admin-only, optional `mailboxId`, `memberId` as ObjectId strings; `422` for invalid filter format)
- `backend/tests/test_models.py`: add mail-request model builder validation tests.
- `backend/tests/test_mail_request_service.py` (new): pure service tests with fake collections for access control, filtering, sort order, and cancel semantics.
- `backend/tests/test_admin_session_auth.py`: add route-level tests for auth gates, payload validation, ownership enforcement, and admin list filters.

### Unit tests (phase-local)
- `backend/tests/test_models.py`
  - `test_build_mail_request_create_requires_expected_sender_or_description`
  - `test_build_mail_request_create_rejects_end_before_start`
  - `test_build_mail_request_create_sets_member_status_and_timestamps`
- `backend/tests/test_mail_request_service.py`
  - `test_create_rejects_unauthorized_mailbox_with_403`
  - `test_member_list_returns_only_active_owned_sorted_desc`
  - `test_cancel_soft_deletes_owned_active_request`
  - `test_cancel_returns_404_for_missing_foreign_or_already_cancelled_request`
  - `test_cancel_uses_single_atomic_update_with_active_status_guard`
  - `test_admin_list_excludes_cancelled_and_applies_filters`
- `backend/tests/test_admin_session_auth.py`
  - member create unauthorized mailbox -> `403`
  - member delete other member request -> `404`
  - member delete already-cancelled request -> `404`
  - member list excludes other members
  - validation failures (`expectedSender`/`description`, invalid date window) -> `400`
  - admin active-list route requires admin session and supports `mailboxId`/`memberId` ObjectId filters
  - admin active-list invalid `memberId` ObjectId -> `422`

## Phase 2: Frontend Member/Admin UI
Affected files and changes
- `frontend/src/lib/api.ts`: add typed contracts and helpers:
  - `ApiMailRequest`, `ApiCreateMailRequestPayload`
  - `createMailRequest(...)`, `listMemberMailRequests()`, `cancelMailRequest(id)`, `listAdminMailRequests(filters?)`
- `frontend/src/pages/member/MemberDashboard.tsx`: add “Expected Mail” section that:
  - builds mailbox dropdown from already-loaded member mailbox summary data
  - supports create form fields (`mailboxId`, `expectedSender`, `description`, `startDate`, `endDate`) with client-side guard for required sender/description
  - loads ACTIVE requests, renders list with mailbox name/date window/created timestamp, and supports cancel action
- `frontend/src/pages/admin/AdminHome.tsx`: add navigation action for expected-mail admin view.
- `frontend/src/pages/admin/AdminMailRequests.tsx` (new): read-only ACTIVE requests table with optional member/mailbox filters and local mapping to member/mailbox display names.
- `frontend/src/App.tsx`: register `/admin/mail-requests` route for admins.
- `frontend/src/pages/member/MemberDashboard.test.tsx` (new or expanded): focused tests for member create/cancel flow wiring.
- `frontend/src/pages/admin/AdminMailRequests.test.tsx` (new): focused tests for active-list fetch/filter rendering behavior.

### Unit tests (phase-local)
- `frontend/src/pages/member/MemberDashboard.test.tsx`
  - blocks submit when both sender and description are empty
  - submits valid create payload and refreshes list
  - cancel action calls API helper with selected request id and removes/refreshes row
- `frontend/src/pages/admin/AdminMailRequests.test.tsx`
  - loads and renders active requests only from API helper response
  - applies filter controls to request query params
  - renders member/mailbox display columns from mapped lookup data

## Phase 3: Mandatory Documentation Updates
Affected files and changes
- `docs/architecture/data-model.md`: add `MAIL_REQUEST` entity definition, field semantics, invariants, and lifecycle state transitions (`ACTIVE -> CANCELLED` only in this ticket), explicitly documenting `memberId` as `users._id` ObjectId reference.
- `docs/architecture/diagrams/data-model.mmd`: add `MAIL_REQUEST` node and relationships to `MAILBOX`/member identity context.
- `docs/api/member-api-contract.md`: document:
  - `POST /api/mail-requests`
  - `GET /api/mail-requests`
  - `DELETE /api/mail-requests/{id}`
  - validation and mailbox-level authorization rules.
- `docs/api/admin-notification-api-contract.md` (rename or split if needed): add `GET /api/admin/mail-requests` contract with optional `mailboxId`/`memberId` ObjectId-string filters, explicit `422` behavior for invalid ObjectId query values, and admin-only behavior.
