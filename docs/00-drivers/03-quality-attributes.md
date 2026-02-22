## 1. Performance

**QA-P1 — Dashboard Load Performance**

An authenticated member (Source) requests weekly mail totals for all authorized mailboxes (Stimulus) under normal operating conditions with up to 500 total members and low concurrency (Environment). The backend aggregation endpoint and database (Artifact) query mail entries using indexed mailboxId and date range filters and return totals (Response), ensuring a 95th percentile response time of no more than 500ms and no request exceeding 1 second under normal load (Response Measure).

**QA-P2 — Weekly Email Job Completion**

The Scheduler container (Source) calls Backend internal HTTP job endpoint for all opted-in members (Stimulus) in a single-instance deployment with up to 500 members (Environment). The backend aggregation and email dispatch logic (Artifact) process each opted-in member and send a summary email (Response), ensuring the entire job completes within 5 minutes while the system remains responsive to API requests during execution (Response Measure).

---

## 2. Reliability

**QA-R1 — Email Provider Failure Isolation**

An email provider (Source) returns an error during an email send attempt (Stimulus) while the weekly job is executing (Environment). The email dispatch logic (Artifact) logs the failure and continues processing remaining members (Response), ensuring that failure of one email does not halt the job, the failure is recorded within 2 seconds, and at least 99 percent of non-failing emails are still delivered (Response Measure).

**QA-R2 — External Identity Source Unavailability**

The Optix API (Source) becomes unavailable and a hydration attempt fails (Stimulus) in production (Environment). The identity sync component (Artifact) logs the failure and preserves the existing internal state (Response), ensuring no existing user or team records are corrupted and that retry is possible without manual database repair (Response Measure).

---

## 3. Security

**QA-S1 — Unauthorized Mailbox Access Attempt**

An authenticated member (Source) attempts to access a mailbox not owned by them or their company (Stimulus) in production (Environment). The authorization layer (Artifact) denies the request (Response), ensuring an HTTP 403 response is returned, no unauthorized data is exposed, and the security event is logged (Response Measure).

---

## 4. Availability

**QA-A1 — Single-Instance Failure**

A host machine failure (Source) causes service containers to stop (Stimulus) in an on-prem deployment (Environment). The system (Artifact) becomes unavailable until the host is restored and containers are relaunched (Response), ensuring MongoDB persistent volume data integrity is preserved and services restart cleanly upon recovery (Response Measure).

---

## 5. Modifiability

**QA-M1 — OCR Provider Replacement**

A developer (Source) introduces a new OCR implementation to replace the existing provider (Stimulus) during development (Environment). The OCR integration layer (Artifact) is updated to support the new provider (Response), ensuring that changes are confined to the OCR abstraction layer and no modifications are required to aggregation logic, mailbox logic, mail entry logic, or the mail persistence model (Response Measure).

QA-M1 remains satisfied after layered architecture refactoring because provider integration points remain in service-level abstractions while repository and model layers stay storage/domain-focused and provider-agnostic.

---

## 6. Observability

**QA-O1 — Weekly Job Failure Visibility**

An unhandled exception (Source) occurs during scheduler-triggered weekly execution (Stimulus) in production (Environment). Scheduler and Backend logs (Artifact) capture the failure with sufficient diagnostic context (Response), ensuring stack trace visibility and that operators can detect failures from logs without direct database inspection (Response Measure).
