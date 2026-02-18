# Open Questions
None.

# Locked Decisions
- Support exactly one special-case template in this ticket: `mail-arrived`.
- `mailboxId` is required; this notification is mailbox-scoped.
- Add operational admin UI trigger in-scope for this ticket.
- Expose only `POST /admin/notifications/special` (no `/api` alias).
- Keep `SpecialCaseNotifier` as a separate intent class and do not reuse `WeeklySummaryNotifier`.

# Task Checklist
## Phase 1
- ☑ Add special-case notification primitives for a single hardcoded `mail-arrived` template and required mailbox context.
- ☑ Implement `SpecialCaseNotifier.notifySpecialCase(userId, mailboxId, triggeredBy="admin")` with validation-first behavior and full attempt logging.
- ☑ Add notifier unit tests for user/mailbox validation failures and send outcomes.

## Phase 2
- ☑ Extend `EmailChannel` to handle special-case payload rendering using centralized `MAIL_ARRIVED_TEMPLATE` config.
- ☑ Add `emails/special_mail_arrived.html` and email-channel unit tests for subject/template/provider behavior.
- ☑ Keep free-form content impossible by construction (no message text input in payload).

## Phase 3
- ☑ Add backend endpoint `POST /admin/notifications/special` with admin auth + strict payload validation.
- ☑ Add admin UI workflow: mailbox selector + “Send Mail Arrived Notification” action + confirm/send result handling.
- ☑ Add backend/frontend unit tests for the new endpoint and UI action flow.

## Phase 1: Special-Case Intent + Logging Model (Single Template)
Affected files and changes
- `backend/services/notifications/types.py`: add `SpecialCaseNotificationPayload` and extend notification log typing for required `mailboxId` and fixed `templateType="mail-arrived"`; extend `NotificationType` with `"special-case"` and `NotifyReason` with `"mailbox_not_found"`.
- `backend/services/notifications/interfaces.py`: extend protocol with `notifySpecialCase(...)` and widen `NotificationChannel.send(...)` payload typing to accept weekly-summary or special-case payload.
- `backend/services/notifications/log_repository.py`: add special-case log insert helper (or generic insert path) that persists `type`, fixed `templateType`, required `mailboxId`, `triggeredBy`, `status`, `reason`, `errorMessage`, `sentAt`, `createdAt`.
- `backend/services/notifications/special_case_notifier.py` (new): implement `SpecialCaseNotifier` with required user/mailbox loading, payload build, channel dispatch, result normalization, and attempt logging.
- `backend/services/notifications/__init__.py`: export `SpecialCaseNotifier` and any new types/helpers.

### Behavior details
- `notifySpecialCase` intent signature:
  - `userId: ObjectId`
  - `mailboxId: ObjectId`
  - `triggeredBy: "admin"`
- Validation-first rules (before channel dispatch):
  - If user missing, return `failed/user_not_found` and log once.
  - If mailbox missing, return `failed/mailbox_not_found` and log once.
  - No channel sends occur for validation failures.
- Logging rules for every invocation:
  - `type="special-case"`
  - `templateType="mail-arrived"`
  - `mailboxId=<required ObjectId>`
  - `triggeredBy="admin"`
  - `sentAt` only for sent outcomes; `errorMessage` set for channel/runtime failures.

### Unit tests (phase-local)
- `backend/tests/test_special_case_notifier.py` (new):
  - `test_notify_special_case_fails_and_logs_when_user_missing`
  - `test_notify_special_case_fails_and_logs_when_mailbox_missing`
  - `test_notify_special_case_does_not_dispatch_channel_on_validation_failure`
  - `test_notify_special_case_logs_sent_when_channel_succeeds`
  - `test_notify_special_case_logs_failed_when_all_channels_fail`
  - `test_notify_special_case_payload_contains_required_mailbox_context`

## Phase 2: Email Rendering for `mail-arrived`
Affected files and changes
- `backend/services/notifications/channels/email_channel.py`: add special-case branch with centralized config:
  - `MAIL_ARRIVED_TEMPLATE = {"subject": "Mail has arrived", "template": "emails/special_mail_arrived.html", "requires_mailbox": True}`
  - render template using user + mailbox context from payload and send via existing provider abstraction.
- `backend/templates/emails/special_mail_arrived.html` (new): predefined content for mail-arrived notification.
- `backend/tests/test_email_channel.py`: add tests for special-case render path and provider failure normalization.

### Rendering/content decisions
- Only one special-case template exists in this ticket and is selected internally.
- No request/body field can alter subject/template/message text.
- Mailbox context is required and rendered in template content.

### Unit tests (phase-local)
- In `backend/tests/test_email_channel.py`:
  - `test_send_special_mail_arrived_renders_template_and_subject`
  - `test_send_special_mail_arrived_includes_mailbox_context`
  - `test_send_special_mail_arrived_returns_failed_when_provider_raises`

## Phase 3: Admin Endpoint + Admin UI Trigger
Affected files and changes
- `backend/app.py`: add `POST /admin/notifications/special`, require admin session, validate `userId` and required `mailboxId`, call `SpecialCaseNotifier.notifySpecialCase(...)`, return notify result.
- `backend/tests/test_admin_session_auth.py`: add auth and payload validation coverage plus notifier invocation assertions.
- `frontend/src/lib/api.ts`: add typed API helper `sendMailArrivedNotification({ userId, mailboxId })` that calls `/admin/notifications/special`.
- `frontend/src/pages/admin/AdminDashboard.tsx` (or split admin component file if needed): add mailbox selector + “Send Mail Arrived Notification” action + confirm/send state + success/error result feedback.
- `docs/architecture/notification-system.md`: add special-case intent and endpoint behavior for `mail-arrived`.
- `docs/api/member-api-contract.md` or a new admin API contract file: document `/admin/notifications/special` request/response.

### Endpoint behavior
- Request payload:
  - `userId: string` (ObjectId, required)
  - `mailboxId: string` (ObjectId, required)
- Backend-internal fixed template metadata:
  - `templateType = "mail-arrived"`
- Response:
  - existing notify result shape (`status`, `reason?`, `channelResults`).

### Unit tests (phase-local)
- `backend/tests/test_admin_session_auth.py` additions:
  - unauthenticated request returns `401`
  - non-admin session returns `403`
  - missing `mailboxId` returns `422`
  - invalid object ids return existing validation errors
  - valid payload calls `SpecialCaseNotifier.notifySpecialCase(userId=<ObjectId>, mailboxId=<ObjectId>, triggeredBy="admin")`
  - success returns `200` with notifier result
- `frontend/src/test/...` (new focused test file near admin page):
  - required mailbox selection enforced before submit
  - submit calls API helper with selected mailbox and target user
  - success and API-error states are surfaced to admin
