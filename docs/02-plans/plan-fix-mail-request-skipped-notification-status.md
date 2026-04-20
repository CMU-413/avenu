# Open Questions
- None.

# Task Checklist
## Phase 1
- ☑ Add `SKIPPED` to mail-request notification status values.
- ☑ Preserve notifier `skipped` outcomes when persisting `MAIL_REQUEST.lastNotificationStatus`.
- ☑ Add backend unit tests for skipped resolve/retry notification paths.

## Phase 2
- ☑ Align frontend API types with the expanded mail-request notification status.
- ☑ Update architecture/docs to define `skipped` semantics consistently across `MAIL_REQUEST` and `NOTIFICATION_LOG`.

## Phase 1: Backend Status Alignment
Affected files and changes
- `backend/models/builders.py`
  - Extend `MAIL_REQUEST_NOTIFICATION_STATUSES` to `{"SENT", "SKIPPED", "FAILED"}`.
  - Keep mail-request lifecycle status handling unchanged.
- `backend/services/mail_request_service.py`
  - Change `_notification_status_from_notify_result` to map notifier outcomes directly:
    - `sent -> "SENT"`
    - `skipped -> "SKIPPED"`
    - `failed` and unexpected values -> `"FAILED"`
  - Reuse the same mapping for both resolve and retry flows so `MAIL_REQUEST.lastNotificationStatus` preserves notifier semantics without changing lifecycle transitions.
- `backend/tests/unit/test_mail_request_service.py`
  - Add resolve and retry cases where `notifySpecialCase()` returns `status="skipped"` and assert `lastNotificationStatus == "SKIPPED"`.
  - Keep existing sent/failed/non-rollback coverage intact.
- `backend/tests/unit/test_models.py`
  - Update enum coverage to assert `MAIL_REQUEST_NOTIFICATION_STATUSES == {"SENT", "SKIPPED", "FAILED"}`.
- `backend/tests/unit/test_admin_session_auth.py`
  - Extend response-shape coverage so admin resolve/retry endpoints accept and return `lastNotificationStatus="SKIPPED"`.

### Unit tests (phase-local)
- `backend/tests/unit/test_mail_request_service.py`
  - `test_resolve_mail_request_sets_last_notification_skipped_metadata_on_skipped_result`
  - `test_retry_notification_sets_last_notification_skipped_metadata_on_skipped_result`
- `backend/tests/unit/test_models.py`
  - `test_mail_request_notification_status_enum`
- `backend/tests/unit/test_admin_session_auth.py`
  - `test_admin_resolve_mail_request_returns_skipped_notification_metadata`
  - `test_admin_retry_notification_returns_skipped_notification_metadata`

## Phase 2: Contract and Documentation Alignment
Affected files and changes
- `frontend/src/lib/api/contracts/types.ts`
  - Expand `ApiMailRequestNotificationStatus` to `"SENT" | "SKIPPED" | "FAILED"`.
  - Update `ApiNotifyChannelResult.status` to include `"skipped"` so notifier result typing matches backend behavior.
- `docs/01-architecture/data-model.md`
  - Update `MAIL_REQUEST.lastNotificationStatus` to `"SENT" | "SKIPPED" | "FAILED" | null`.
  - Clarify that `SKIPPED` means no notification was sent and no delivery failure occurred.
- `docs/01-architecture/notification-system.md`
  - Define `skipped` as an intentional non-send for mail-arrived notifications, including opt-out and all-channel-skip cases.
  - Align the resolve/retry flow description with the expanded `MAIL_REQUEST.lastNotificationStatus`.
- `docs/01-architecture/diagrams/data-model.mmd`
  - Update the `MAIL_REQUEST.lastNotificationStatus` enum to include `SKIPPED`.

### Unit tests (phase-local)
- No additional unit tests in this phase; contract and documentation alignment only.
