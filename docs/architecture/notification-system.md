# Avenu Notification System Design

## Overview

The notification system supports two admin/scheduled intents with shared notifier abstractions:

- Weekly summaries via `WeeklySummaryNotifier`
- Mail-arrived notifications via `SpecialCaseNotifier`

Separation of concerns:

- Intent: notifier classes determine *what* to send
- Channel: `EmailChannel` handles rendering + channel-level send semantics
- Provider: email providers handle transport-only concerns

## Deployment Context

- Scheduler runs in its own container and calls backend HTTP endpoints.
- Backend executes all notification business logic and provider integration.
- Scheduler does not access database collections directly.

## Trigger Paths

### Scheduler-triggered weekly summary

1. Scheduler calls `POST /api/internal/jobs/weekly-summary`.
2. Backend validates scheduler token and idempotency key.
3. Backend runs weekly summary orchestration and dispatches through `WeeklySummaryNotifier`.

### Admin-triggered mail-arrived notifications

Mail-arrived notifications are triggered exclusively by expected-mail request workflow endpoints:

- `POST /api/admin/mail-requests/{id}/resolve`
- `POST /api/admin/mail-requests/{id}/retry-notification`

No standalone admin special notification endpoint is used for mail-arrived sends.

## Weekly Summary Flow

1. Resolve target week bounds.
2. Select opted-in users.
3. Build summary via `MailSummaryService`.
4. Dispatch across configured channels.
5. Record attempt outcome in `NOTIFICATION_LOG`.

## Mail-Arrived Flow (Resolve/Retry)

1. Resolve flow transitions request lifecycle to `RESOLVED` when request is currently `ACTIVE`.
2. Backend invokes `SpecialCaseNotifier.notifySpecialCase(userId, triggeredBy="admin")`.
3. Notification outcome is persisted on `MAIL_REQUEST`:
   - `lastNotificationStatus = "SENT" | "FAILED"`
   - `lastNotificationAt = datetime`
4. Retry flow re-invokes notifier without lifecycle mutation.

Failure policy:

- Notification failures do not roll back mail-request resolution.
- Notifier failures are explicitly logged in `NOTIFICATION_LOG` (`type="special-case"`, `templateType="mail-arrived"`).

## Public API Scope

Public API docs cover member/admin endpoints only.

- Internal endpoint `POST /api/internal/jobs/weekly-summary` remains deployment-facing.
- Member/admin endpoint contracts are documented in `docs/api/*`.
