## 1. System Purpose

Avenu manages physical mail intake for a coworking space.

The system enables:

* Admins to log incoming mail
* Members to view mail associated with them or their company
* Weekly summary email notifications

---

## 2. Actors

### 2.1 Admin

Staff responsible for logging and managing mail.

### 2.2 Member

Coworking user who may receive:

* Personal mail
* Company mail (if part of a company/team)

---

## 3. Mailbox Model

FR-1
The system shall represent mail ownership via a **Mailbox** entity.

FR-2
A mailbox shall correspond to either:

* A personal member, or
* A company

FR-3
Each mailbox shall have a display name for search and rendering.

FR-4
Members shall have access to:

* Their personal mailbox
* All company mailboxes associated with companies they belong to

FR-5
Admins shall have access to all mailboxes.

---

## 4. Authentication & Authorization

FR-6
All member-facing functionality shall require authentication.

FR-7
Authorization shall enforce mailbox-level access boundaries.

FR-8
Admin functionality shall require elevated privileges.

---

## 5. Mail Logging

FR-9
Admins shall be able to create a mail entry containing:

* Mailbox identifier
* Date received
* Mail type (letter or package)
* Count

FR-10
Mail entries shall be stored persistently.

FR-11
The system shall allow mail entries to be retrieved by mailbox and date range.

---

## 6. OCR Assistance (Optional)

FR-12
Admins shall be able to upload an image of incoming mail.

FR-13
The system shall attempt to extract mailbox-identifying information via OCR.

FR-14
If OCR confidence is insufficient, the system shall require manual confirmation before assignment.

---

## 7. Mail Aggregation

FR-15
The system shall compute weekly totals for each mailbox, including:

* Total letters
* Total packages

FR-16
Aggregation logic shall be deterministic and based on a fixed weekly time window.

FR-17
The aggregation logic used in email summaries shall match the aggregation logic used in the dashboard.

---

## 8. Member Dashboard

FR-18
Members shall be able to view weekly totals for all mailboxes they are authorized to access.

FR-19
Dashboard totals shall reflect persisted mail entries.

---

## 9. Weekly Email Notifications

FR-20
Members shall be able to opt in or opt out of weekly summary emails.

FR-21
The system shall execute a scheduled weekly job.

FR-22
For each opted-in member, the system shall:

* Aggregate mail totals for the defined week
* Send a summary email

FR-23
Summary email content shall include:

* Week range
* Total letters
* Total packages

FR-24
Failure to send one member’s email shall not prevent processing of other members.

FR-25
Email send failures shall be logged.

---

## 10. Data Synchronization (Optix Integration)

FR-26
The system shall ingest user and team data from the external source.

FR-27
User records shall be uniquely identified by external ID.

FR-28
Team/company records shall be uniquely identified by external ID.

FR-29
The system shall upsert users and teams to maintain referential integrity.

---

## 11. Non-Goals (Functional)

The system shall not:

* Provide real-time push notifications
* Manage billing
* Support multi-location tenancy
* Guarantee guaranteed email delivery semantics
