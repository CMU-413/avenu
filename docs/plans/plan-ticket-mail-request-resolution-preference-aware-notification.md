# Open Questions
- None.

# Task Checklist
## Phase 1
- ☑ Extend `MAIL_REQUEST` lifecycle to include `RESOLVED` and notification outcome fields (`lastNotificationStatus`, `lastNotificationAt`).
- ☑ Add atomic backend resolve + notify service (`resolve_mail_request_and_notify`) that persists notification result metadata.
- ☑ Add admin resolve and retry-notification endpoints; extend member status-filtered list endpoint contract enforcement.
- ☑ Remove `POST /api/admin/notifications/special` mail-arrived trigger endpoint.
- ☑ Add backend unit tests for resolution transitions, retry behavior, and notification-failure non-rollback semantics.

## Phase 2
- ☐ Add admin mail logging resolve UI in `RecordEntry` with selected-date window matching and “Resolve & Notify” action.
- ☐ Add retry-notification action in admin request views where notification metadata is shown.
- ☐ Add frontend API helpers/types for resolve/retry endpoints and member `status` filtering.
- ☐ Add member dashboard ACTIVE/RESOLVED toggle and resolved-row rendering (`resolvedAt` visible, no cancel).
- ☐ Update frontend unit tests for resolve/retry flows and member resolved filtering behavior.

## Phase 3
- ☐ Update architecture data model docs for `RESOLVED`, resolve metadata, notification metadata, and lifecycle transitions.
- ☐ Update member/admin API docs for resolve + retry endpoints, status query behavior, and `404`/`422` semantics.
- ☐ Update notification architecture/docs to state mail-arrived notifications are triggered exclusively by resolve/retry workflows.

## Phase 1: Backend Lifecycle + Resolve/Retry Notification API
Affected files and changes
- `backend/models.py`
  - Extend `MAIL_REQUEST_STATUSES` to include `RESOLVED`.
  - Add `MAIL_REQUEST_NOTIFICATION_STATUSES = {"SENT", "FAILED"}`.
  - Extend mail-request model/builder validation expectations to support persisted notification metadata fields:
    - `lastNotificationStatus: "SENT" | "FAILED" | null`
    - `lastNotificationAt: datetime | null`
  - Keep lifecycle semantics independent from notification status fields.
- `backend/services/mail_request_service.py`
  - Add `resolve_mail_request_and_notify(*, request_id: ObjectId, admin_user: dict[str, Any], notifier: SpecialCaseNotifier | None = None) -> dict[str, Any]`.
  - Implement guarded atomic lifecycle transition update on `{ _id: request_id, status: "ACTIVE" }` setting:
    - `status: "RESOLVED"`
    - `resolvedAt: now`
    - `resolvedBy: admin_user["_id"]`
    - `updatedAt: now`
  - Return `APIError(404, "mail request not found")` for missing/non-ACTIVE records.
  - After transition, invoke notifier for the request member; persist notification outcome back onto the same request:
    - success -> `lastNotificationStatus="SENT"`, `lastNotificationAt=now`
    - failure/exception -> `lastNotificationStatus="FAILED"`, `lastNotificationAt=now`
  - Guarantee resolution remains committed even when notification fails; never roll back lifecycle state.
  - Add `retry_mail_request_notification(*, request_id: ObjectId, admin_user: dict[str, Any], notifier: SpecialCaseNotifier | None = None) -> dict[str, Any]`:
    - admin-only service usage
    - no lifecycle mutation (`status`, `resolvedAt`, `resolvedBy` unchanged)
    - re-invokes notifier and updates only `lastNotificationStatus`, `lastNotificationAt`, `updatedAt`
    - returns updated request notification metadata payload
  - Replace member list helper with status-aware method:
    - `list_member_mail_requests(user, status_filter: Literal["ACTIVE", "RESOLVED", "ALL"])`
    - `ALL` maps to `$in: ["ACTIVE", "RESOLVED"]`
- `backend/app.py`
  - Add `POST /api/admin/mail-requests/<id>/resolve` (admin-only) returning updated mail request document including:
    - lifecycle fields (`status`, `resolvedAt`, `resolvedBy`)
    - notification fields (`lastNotificationStatus`, `lastNotificationAt`)
  - Add `POST /api/admin/mail-requests/<id>/retry-notification` (admin-only) returning updated notification metadata on the request.
  - Extend `GET /api/mail-requests` to parse `status` query (`ACTIVE|RESOLVED|ALL`, default `ACTIVE`), `422` on invalid values.
  - Remove `POST /api/admin/notifications/special` route entirely.
- `backend/services/notifications/log_repository.py`
  - Ensure notifier failures/successes are explicitly logged for resolve/retry-triggered sends (via existing special-case logging path).
- `backend/tests/test_mail_request_service.py`
  - Add service tests for resolve success/failure, notification metadata persistence, retry behavior, and non-rollback guarantees.
- `backend/tests/test_admin_session_auth.py`
  - Add route tests for resolve and retry endpoints auth/error handling and response shape.
  - Remove/replace tests covering deleted `/api/admin/notifications/special` endpoint.
- `backend/tests/test_special_case_notifier.py`
  - Keep notifier logging assertions; extend where needed to validate explicit failure logging on channel failure/exception remains intact.
- `backend/tests/test_models.py`
  - Add/adjust status enum and notification metadata field expectations.

### Unit tests (phase-local)
- `backend/tests/test_mail_request_service.py`
  - `test_resolve_mail_request_sets_resolved_fields_and_returns_updated_doc`
  - `test_resolve_mail_request_sets_last_notification_sent_metadata_on_success`
  - `test_resolve_mail_request_sets_last_notification_failed_metadata_on_failure_without_rollback`
  - `test_resolve_mail_request_returns_404_when_missing_or_not_active`
  - `test_retry_notification_updates_last_notification_metadata_without_lifecycle_change`
  - `test_retry_notification_returns_404_when_request_missing`
  - `test_member_list_status_active_returns_active_only`
  - `test_member_list_status_resolved_returns_resolved_only`
  - `test_member_list_status_all_returns_active_and_resolved_only`
- `backend/tests/test_admin_session_auth.py`
  - `test_admin_resolve_mail_request_requires_admin_session`
  - `test_admin_resolve_mail_request_returns_updated_mail_request_payload`
  - `test_admin_resolve_mail_request_returns_404_for_resolved_or_cancelled`
  - `test_admin_retry_notification_requires_admin_session`
  - `test_admin_retry_notification_returns_updated_notification_metadata`
  - `test_member_mail_requests_status_filter_defaults_to_active`
  - `test_member_mail_requests_status_filter_rejects_invalid_value_with_422`
  - remove `admin_special_notification_*` coverage tied to deleted endpoint
- `backend/tests/test_special_case_notifier.py`
  - `test_notify_special_case_logs_failed_when_all_channels_fail`
  - `test_notify_special_case_logs_sent_when_channel_succeeds`

## Phase 2: Frontend Admin Resolve/Retry Flow + Member Resolved View
Affected files and changes
- `frontend/src/lib/api.ts`
  - Expand `ApiMailRequestStatus` to `"ACTIVE" | "CANCELLED" | "RESOLVED"`.
  - Add notification metadata fields to `ApiMailRequest`:
    - `lastNotificationStatus: "SENT" | "FAILED" | null`
    - `lastNotificationAt: string | null`
  - Keep resolved fields on `ApiMailRequest`: `resolvedAt`, `resolvedBy`.
  - Extend `listMemberMailRequests(params?: { status?: "ACTIVE" | "RESOLVED" | "ALL" })`.
  - Add:
    - `resolveAdminMailRequest(id: string): Promise<ApiMailRequest>`
    - `retryAdminMailRequestNotification(id: string): Promise<Pick<ApiMailRequest, "id" | "lastNotificationStatus" | "lastNotificationAt">>`
  - Remove `sendMailArrivedNotification` client helper.
- `frontend/src/pages/admin/RecordEntry.tsx`
  - Fetch active expected-mail requests for selected mailbox.
  - Apply date-window matching using selected `RecordEntry.date` as the reference day:
    - include requests with no window
    - include when `startDate <= date <= endDate` (with open-ended bounds handled)
  - Render side panel with sender, description, date window, and notification metadata.
  - Add row actions:
    - `Resolve & Notify` for ACTIVE rows
    - `Retry Notification` where applicable after resolution
  - On resolve success, remove resolved request from ACTIVE panel and show success toast.
  - On retry, update displayed notification metadata in-place.
- `frontend/src/pages/admin/AdminMailRequests.tsx`
  - Show `lastNotificationStatus` / `lastNotificationAt` columns where request status/metadata is available.
  - Add retry notification action for resolved entries if this screen is expanded beyond ACTIVE-only listing.
- `frontend/src/pages/admin/AdminNotifications.tsx`
  - Remove mail-arrived send controls and related logic; keep weekly summary functionality only.
- `frontend/src/pages/admin/AdminHome.tsx`
  - Remove navigation wording/action that implies standalone mail-arrived sends.
- `frontend/src/App.tsx`
  - Remove route usage dependencies tied to deleted mail-arrived special endpoint UI behavior (if any).
- `frontend/src/pages/member/MemberDashboard.tsx`
  - Add ACTIVE/RESOLVED toggle, default ACTIVE.
  - Query with `status` param.
  - Render resolved rows with sender, description, date window, `createdAt`, `resolvedAt`; no cancel action on resolved rows.
- `frontend/src/pages/admin/RecordEntry.test.tsx` (new)
  - Add focused tests for selected-date matching, resolve action wiring, retry wiring, and metadata refresh.
- `frontend/src/pages/member/MemberDashboard.test.tsx`
  - Extend tests for status toggle and resolved rendering constraints.
- `frontend/src/pages/admin/AdminNotifications.test.tsx`
  - Update tests to weekly-only behavior.

### Unit tests (phase-local)
- `frontend/src/pages/admin/RecordEntry.test.tsx`
  - renders matching ACTIVE requests based on selected `date` window
  - excludes requests outside selected `date` window
  - clicking `Resolve & Notify` calls resolve API and removes row
  - clicking retry updates notification metadata (`lastNotificationStatus`, `lastNotificationAt`)
- `frontend/src/pages/member/MemberDashboard.test.tsx`
  - default expected-mail query uses `status=ACTIVE`
  - selecting resolved view requests `status=RESOLVED`
  - resolved entries render `resolvedAt` and do not render cancel button
- `frontend/src/pages/admin/AdminNotifications.test.tsx`
  - weekly notification flow still works
  - mail-arrived controls are not rendered

## Phase 3: Mandatory Documentation Updates
Affected files and changes
- `docs/architecture/data-model.md`
  - Update `MAIL_REQUEST` lifecycle to `ACTIVE | CANCELLED | RESOLVED`.
  - Add fields:
    - `resolvedAt`, `resolvedBy`
    - `lastNotificationStatus`, `lastNotificationAt`
  - Document invariants:
    - `resolvedAt`/`resolvedBy` required when `status=RESOLVED`
    - notification metadata is operational and does not affect lifecycle transitions.
- `docs/architecture/diagrams/data-model.mmd`
  - Update `MAIL_REQUEST` node with resolved and notification metadata fields.
- `docs/api/member-api-contract.md`
  - Update `GET /api/mail-requests` status filter contract (`ACTIVE` default, `RESOLVED`, `ALL`, invalid => `422`).
  - Clarify member cancel restriction to ACTIVE only; cancelling RESOLVED returns `404`.
- `docs/api/admin-notification-api-contract.md`
  - Remove `POST /api/admin/notifications/special` from contract.
  - Add `POST /api/admin/mail-requests/{id}/resolve` with updated mail request response payload including notification metadata.
  - Add `POST /api/admin/mail-requests/{id}/retry-notification` contract and response semantics.
- `docs/architecture/notification-system.md`
  - Clarify that mail-arrived notifications are triggered exclusively via expected-mail resolve/retry workflows.
  - Document explicit notifier failure logging expectation and non-rollback resolution behavior.

### Unit tests (phase-local)
- No additional unit tests in this phase; documentation-only changes.
