# Avenu Notification System Design

## Overview

This document defines the architecture and design decisions for the Avenu notification system, starting with Weekly Mail Summary notifications.

The system is designed to:

- Support cron-triggered and admin-triggered notifications
- Be channel-agnostic (email now, SMS later)
- Separate domain logic from transport logic
- Allow provider swapping without touching business logic
- Prevent duplicated sends

This establishes a scalable notification foundation for future expansion (SMS, urgent alerts, OCR-triggered events).

---

# Architectural Principles

1. **Intent over Transport**
   - Code should express “notify weekly summary”, not “send email”.
   - Email is a delivery channel, not the core abstraction.

2. **Separation of Concerns**
   - Aggregation logic must not know about email.
   - Channels must not compute domain data.
   - Providers must not leak into application layers.

3. **Single Entry Point**
   - Cron and Admin triggers must call the same notifier.
   - No duplicated logic across execution paths.

4. **Provider Isolation**
   - Only one file imports the email provider SDK.
   - Swapping providers requires zero business logic changes.

---

# High-Level Architecture

```

Cron / Admin
→ WeeklySummaryNotifier (intent layer)
→ MailSummaryService (aggregation)
→ NotificationChannel[]
→ EmailChannel
→ EmailProvider (Resend adapter)

````

---

# Core Components

---

## 1. MailSummaryService (Domain Layer)

### Responsibility
Compute weekly mail summary for a user.

### Interface

```ts
getWeeklySummary(userId, weekStart, weekEnd)
````

### Returns

Structured summary object:

```ts
{
  weekStart: Date,
  weekEnd: Date,
  totalLetters: number,
  totalPackages: number,
  mailboxes: [
    {
      mailboxName: string,
      letters: number,
      packages: number,
      dailyBreakdown: [
        { date, letters, packages }
      ]
    }
  ]
}
```

### Design Decisions

* No email formatting.
* No template logic.
* Deterministic ordering:

  * Date ASC
  * Mailbox ASC
* Same logic used by:

  * Member dashboard
  * Email notifications

---

## 2. Notifier Interface (Intent Layer)

### Purpose

Represent notification intent without tying to any transport.

### Interface

```ts
interface Notifier {
  notifyWeeklySummary(params: WeeklySummaryParams): Promise<NotifyResult>
}
```

### Params

```ts
{
  userId: string
  weekStart: Date
  weekEnd: Date
  triggeredBy: "cron" | "admin"
}
```

### NotifyResult

```ts
{
  status: "sent" | "skipped" | "failed"
  channelResults?: ChannelResult[]
}
```

### Design Decisions

* Cron and Admin both call this.
* No provider imports.
* Handles:

  * Preference checks
  * Aggregation
  * Channel dispatch
  * Logging

---

## 3. WeeklySummaryNotifier

### Responsibilities

* Load user
* Check notification preference
* Call MailSummaryService
* Skip empty summaries (MVP decision)
* Dispatch to configured channels
* Log notification result

### Behavior Rules

* Skip if `emailNotificationsEnabled = false`
* Skip if total mail count = 0
* Do not throw if one channel fails
* Always log attempt

---

## 4. NotificationChannel Abstraction

### Interface

```ts
interface NotificationChannel {
  send(payload: NotificationPayload): Promise<ChannelResult>
}
```

### ChannelResult

```ts
{
  channel: "email" | "sms"
  status: "sent" | "failed"
  error?: string
}
```

### Design Decisions

* Channel is transport-specific.
* Channel does not fetch domain data.
* Channel does not know about cron/admin.

---

## 5. EmailChannel

### Responsibilities

* Render weekly summary template
* Generate subject line
* Call EmailProvider
* Catch and return errors

### Subject Format

```
Your Avenu Mail Summary (Feb 10–16)
```

### Design Decisions

* HTML rendering lives here.
* EmailChannel is unaware of Resend.
* Receives provider via dependency injection.

---

## 6. EmailProvider (Resend Adapter)

### Interface

```ts
interface EmailProvider {
  send({ to, subject, html }): Promise<{ messageId: string }>
}
```

### Implementation

```
ResendProvider implements EmailProvider
```

### Design Decisions

* Only file importing Resend SDK.
* Swappable with Postmark, SendGrid, etc.
* No domain logic here.

---

# Notification Logging

## Table: NOTIFICATION_LOG

Fields:

* id
* userId
* type ("weekly-summary")
* weekStart
* status
* triggeredBy ("cron" | "admin")
* errorMessage
* sentAt

## Design Decisions

* Every attempt logged.
* Required for idempotency.
* Enables debugging and audit trail.

---

# Cron Job Design

### Behavior

* Runs every Monday at fixed time.
* Computes deterministic previous week boundaries.
* Fetches all opted-in users.
* Calls WeeklySummaryNotifier per user.
* Continues on failure.

### Idempotency

Must prevent duplicate sends.

Approach:

* Before sending, check NOTIFICATION_LOG for (userId + weekStart).
* Skip if already sent.

---

# Admin Trigger

### Endpoint

```
POST /admin/notifications/summary
```

### Behavior

* Accepts:

  * userId
  * weekStart
  * weekEnd
* Calls WeeklySummaryNotifier
* Returns NotifyResult
* Uses same code path as cron

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
