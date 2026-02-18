## 1. Performance

### QA-P1 — Dashboard Load Performance

**Source of stimulus**
Authenticated member

**Stimulus**
Requests weekly mail totals for all authorized mailboxes

**Environment**
Normal operating conditions; up to 500 total members; low concurrency

**Artifact**
Backend aggregation endpoint + database

**Response**
System queries mail entries using indexed mailboxId + date range filters and returns totals

**Response Measure**

* 95th percentile response time ≤ 500ms
* No request exceeds 1 second under normal load

---

### QA-P2 — Weekly Email Job Completion

**Source of stimulus**
Internal scheduler

**Stimulus**
Triggers weekly summary job for all opted-in members

**Environment**
≤ 500 members; single-instance deployment

**Artifact**
Aggregation logic + email dispatch logic

**Response**
System processes each opted-in member and sends summary email

**Response Measure**

* Entire job completes within 5 minutes
* System remains responsive to API requests during execution

---

## 2. Reliability

### QA-R1 — Email Provider Failure Isolation

**Source of stimulus**
Email provider

**Stimulus**
Email send attempt returns error

**Environment**
Weekly job executing

**Artifact**
Email dispatch logic

**Response**
System logs failure and continues processing remaining members

**Response Measure**

* Failure of one email does not halt job
* Failure recorded within 2 seconds
* ≥ 99% of non-failing emails still delivered

---

### QA-R2 — External Identity Source Unavailability

**Source of stimulus**
Optix API unavailable

**Stimulus**
Hydration attempt fails

**Environment**
Production

**Artifact**
Identity sync component

**Response**
System logs failure and preserves existing internal state

**Response Measure**

* No existing user/team records corrupted
* Retry possible without manual database repair

---

## 3. Security

### QA-S1 — Unauthorized Mailbox Access Attempt

**Source of stimulus**
Authenticated member

**Stimulus**
Attempts to access mailbox not owned by them or their company

**Environment**
Production

**Artifact**
Authorization layer

**Response**
System denies request

**Response Measure**

* HTTP 403 returned
* No unauthorized data leakage
* Security event logged

---

## 4. Availability

### QA-A1 — Single-Instance Failure

**Source of stimulus**
Host machine failure

**Stimulus**
Backend container stops

**Environment**
On-prem deployment

**Artifact**
Entire system

**Response**
System becomes unavailable until host restored

**Response Measure**

* Data integrity preserved
* System restarts cleanly when containers are relaunched

---

## 5. Modifiability

### QA-M1 — OCR Provider Replacement

**Source of stimulus**
Developer decision to change OCR provider

**Stimulus**
New OCR implementation introduced

**Environment**
Development

**Artifact**
OCR integration layer

**Response**
New provider can be integrated without modifying aggregation, mailbox, or mail entry logic

**Response Measure**

* Changes confined to OCR abstraction layer
* No modifications required to mail persistence model

---

## 6. Observability

### QA-O1 — Weekly Job Failure Visibility

**Source of stimulus**
Unhandled exception during weekly job

**Stimulus**
Runtime error

**Environment**
Production

**Artifact**
Scheduler + logging system

**Response**
Error logged with sufficient context to diagnose

**Response Measure**

* Log entry includes stack trace
* Failure detectable within log review without database inspection
