# Avenu Notification System Design

## Overview

The notification system supports two admin/scheduled intents with shared notifier abstractions:

- Weekly summaries via `WeeklySummaryNotifier`
- Mail-arrived notifications via `SpecialCaseNotifier`

Separation of concerns:

- Intent: notifier classes determine *what* to send
- Channel: `EmailChannel` and `SMSChannel` handle rendering/formatting and channel-level semantics
- Provider: transport integrations (`MSGraphEmailProvider`, `TwilioSMSProvider`) handle delivery concerns only

## Channel Composition

Backend notifier wiring always includes both channels:

- `email`
- `sms`

Dispatch is user preference-aware:

- `email` channel attempts only when `"email"` is present in `user.notifPrefs`
- `sms` channel attempts only when `"text"` is present in `user.notifPrefs`

No channel preference implies another channel.

## Status Semantics

After channel dispatch:

- top-level `sent` when any channel result is `sent`
- top-level `failed` when no channel sends and at least one channel fails
- top-level `skipped` when all attempted channels are `skipped`

Failure isolation:

- per-channel/provider failures do not halt other channel attempts
- notifier returns structured `channelResults` for each attempted channel

## Logging Semantics

`NOTIFICATION_LOG` remains one row per notifier invocation (not per channel).

- weekly summary sends log `type="weekly-summary"`
- mail-arrived sends log `type="special-case"`, `templateType="mail-arrived"`
- failed attempts may aggregate channel/provider errors into `errorMessage`

## Deployment Context

- Scheduler runs in its own container and calls backend HTTP endpoints.
- Backend executes all notification business logic and provider integration.
- Scheduler does not access database collections directly.
- Backend uses external providers for notifications:
  - Microsoft Graph for email
  - Twilio for SMS

## Trigger Paths

### Scheduler-triggered weekly summary

1. Scheduler calls `POST /api/internal/jobs/weekly-summary`.
2. Backend validates scheduler token and idempotency key.
3. Backend runs weekly summary orchestration and dispatches through `WeeklySummaryNotifier`.

HTTP boundary coverage:

- `POST /api/internal/jobs/weekly-summary` is covered by backend HTTP integration tests for:
  - scheduler token enforcement (`401` on missing/invalid token),
  - idempotency replay behavior,
  - continue-on-failure delivery semantics with persisted `NOTIFICATION_LOG` outcomes.

### Admin-triggered mail-arrived notifications

Mail-arrived notifications are triggered exclusively by expected-mail request workflow endpoints:

- `POST /api/admin/mail-requests/{id}/resolve`
- `POST /api/admin/mail-requests/{id}/retry-notification`

No standalone admin special notification endpoint is used for mail-arrived sends.

## Weekly Summary Flow

1. Resolve target week bounds.
2. Select weekly-summary candidate users from channel-relevant preferences.
3. Build summary via `MailSummaryService`.
4. Filter channels by user `notifPrefs` and dispatch across preferred channels.
5. Record one attempt outcome in `NOTIFICATION_LOG`.

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
