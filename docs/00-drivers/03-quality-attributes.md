# 1. Security

## QA-S1 — Mailbox Access Boundary Enforcement

An authenticated member (Source) attempts to read or mutate mail entries, mail requests, or weekly aggregates for a mailbox they are not authorized to access (Stimulus) in production (Environment). The authorization layer within the controller/service boundary (Artifact) validates mailbox ownership before any repository call (Response), ensuring:

* An HTTP 403 response is returned
* No unauthorized data is exposed
* No unauthorized state mutation occurs
* The event is logged

(Response Measure)

This enforces the invariant defined in FR-4, FR-7, FR-29, and FR-41 .

---

# 2. Reliability

## QA-R1 — Notification Failure Isolation

During weekly summary execution or mail-request resolution (Environment), the email provider (Source) returns an error while sending a notification for a specific member (Stimulus). The notification orchestration logic (Artifact) logs the failure and continues processing remaining recipients (Response), ensuring:

* Failure of one notification does not halt job execution
* Mail-request resolution is not rolled back
* All subsequent eligible members are still processed
* The failure is persisted in `NOTIFICATION_LOG`

(Response Measure)

This enforces FR-24 and FR-35  and aligns with the notification design .

---

## QA-R2 — External Identity Unavailability Safety

The external identity provider (Optix) (Source) becomes unavailable during a user or team synchronization attempt (Stimulus) in production (Environment). The identity synchronization component (Artifact) fails safely (Response), ensuring:

* No partial writes corrupt referential integrity
* Existing user and mailbox associations remain valid
* The failed attempt is logged
* A retry can be executed without manual database repair

(Response Measure)

This enforces TC-3.1 and FR-42–45 .

---

## QA-R3 — Cross-Channel Aggregation Integrity

A member views weekly totals in the dashboard and receives the weekly summary email for the same mailbox set and time window (Environment). The system (Artifact) computes totals via a single shared aggregation service used by both dashboard and email flows (Response), ensuring:

* Identical totals for letters and packages
* Identical week boundary interpretation
* No duplicate aggregation logic across controllers or notifiers

(Response Measure)

This enforces FR-15, FR-16, and FR-17 .

---

# 3. Modifiability

## QA-M1 — External Provider Replacement Isolation

A developer (Source) replaces an external provider implementation (for example OCR or email transport) (Stimulus) during development (Environment). The provider abstraction and service wiring layers (Artifact) are updated (Response), ensuring:

* No modifications are required to repository or domain model layers
* No changes are required to aggregation logic
* HTTP controller contracts remain unchanged

(Response Measure)

This aligns with the layered architecture and provider isolation model .
