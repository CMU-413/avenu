# Avenu Notification System Design

## Overview

The notification system supports weekly summary and special-case notifications with clear separation between:

- Intent (`WeeklySummaryNotifier`, `SpecialCaseNotifier`)
- Channel (`EmailChannel`)
- Provider (`EmailProvider` implementations)

## Deployment Context

- Scheduler runs in its own container and triggers notifications by calling Backend HTTP.
- Backend executes notification business logic and all provider integrations.
- Scheduler does not access the database.

## Trigger Paths

### Scheduler-triggered weekly summary

1. Scheduler container calls:
   - `POST /api/internal/jobs/weekly-summary`
2. Backend validates internal scheduler token and idempotency key.
3. Backend runs weekly job orchestration and delegates to `WeeklySummaryNotifier`.

### Admin-triggered notifications

- Admin routes in backend trigger the same notifier abstractions for admin workflows.

## Core Design Principles

1. Intent over transport:
   - Business code expresses notification intent, not provider-specific sends.
2. Channel/provider isolation:
   - Channel handles template/render and provider invocation.
   - Provider handles API transport only.
3. Shared notifier path:
   - Scheduler and admin flows reuse notifier semantics.
4. Idempotency:
   - Weekly summary delivery is guarded against duplicate sends.

## Weekly Summary Flow

1. Resolve target week bounds.
2. Select opted-in users.
3. Build summary via `MailSummaryService`.
4. Dispatch across configured channels.
5. Record outcome in notification logs.

Failure policy:

- Per-user/provider failure is logged and does not stop processing remaining users.

## Internal Endpoint Scope

- `POST /api/internal/jobs/weekly-summary` is an internal deployment endpoint used by Scheduler container.
- It is intentionally excluded from public member/admin API contract documentation.

## Public API Scope

Public API docs cover user/admin-facing endpoints only. Internal scheduler endpoint behavior is documented in architecture/deployment docs, not public API contracts.

  * userId
* Calls `SpecialCaseNotifier.notifySpecialCase(...)`.
* Uses a single fixed template type in this phase: `mail-arrived`.
* Uses user-level dispatch (not mailbox-level) and does not dispatch channels when user validation fails.
* Logs every attempt in `NOTIFICATION_LOG` with:
  * `type="special-case"`
  * `templateType="mail-arrived"`
  * `triggeredBy="admin"`

---

# Decisions Made

| Decision                      | Rationale                             |
| ----------------------------- | ------------------------------------- |
| Channel-agnostic architecture | Enables SMS later without refactor    |
| Provider adapter pattern      | Allows vendor swapping                |
| Single notifier entrypoint    | Prevents logic duplication            |
| Skip zero-mail weeks          | Reduces unnecessary emails            |
| Deterministic week boundaries | Avoids ambiguity                      |
| Explicit notification log     | Enables idempotency and observability |

---

# Out of Scope (Current Phase)

* SMS implementation
* Urgent item notifications
* OCR-triggered notifications
* Multi-channel user preference matrix

---

# Future Expansion Path

To add SMS:

1. Implement `SmsChannel implements NotificationChannel`
2. Inject into WeeklySummaryNotifier
3. Add user channel preference logic

No changes required to:

* Cron
* Admin endpoint
* Aggregation service

---

# Summary

The notification system is:

* Intent-driven
* Channel-agnostic
* Provider-isolated
* Cron-compatible
* Admin-trigger-compatible
* Idempotent
* Extensible

This foundation supports weekly mail summaries today and multi-channel notifications tomorrow without structural refactor.
