Below is a clean, professional draft of:

`docs/architecture/overview.md`

It reflects:

* Single `app` container (nginx + Flask + frontend)
* Separate MongoDB container
* Scheduled identity sync
* Scheduled weekly email job
* Reverse proxy topology
* Modular monolith backend
* Alignment with your three-pillar model

---

# Architecture Overview

## 1. Architectural Style

Avenu is implemented as a **modular monolith** deployed as a single application container.

The system favors:

* Operational simplicity
* Minimal infrastructure
* Single-instance deployment
* Clear internal module boundaries

No distributed services, message queues, or horizontal scaling mechanisms are required at the current scale.

---

## 2. Deployment Topology

The system consists of two containers:

### 2.1 Application Container (`app`)

Contains:

* Nginx (reverse proxy)
* Flask backend (API + scheduled jobs)
* Static frontend build artifacts

This container exposes a single public port.

### 2.2 Database Container (`mongodb`)

* MongoDB instance
* Persistent volume for data storage

All application persistence flows through this container.

---

## 3. Backend Structure

The backend is logically divided into internal modules:

* Identity Sync Module
  Handles scheduled synchronization with Optix and authoritative user/team hydration.

* Mailbox Module
  Defines ownership boundaries and authorization checks.

* Mail Logging Module
  Persists mail entries and integrates OCR.

* Aggregation Module
  Computes weekly totals for dashboard and notifications.

* Notification Module
  Executes scheduled weekly summary emails.

These modules exist within a single service and communicate in-process.

---

## 4. Scheduled Jobs

Two scheduled processes run inside the backend:

### 4.1 Identity Synchronization

* Periodically pulls user and team data from Optix.
* Upserts records locally.
* Treats Optix identifiers as authoritative.

This decouples identity freshness from user login events.

### 4.2 Weekly Email Job

* Runs on a fixed schedule.
* Aggregates weekly totals.
* Sends summary emails to opted-in members.
* Logs failures without halting processing.

No external scheduler or distributed coordination is required under current constraints.

---

## 5. Data Ownership Model

The system uses a **Mailbox** abstraction as the ownership and authorization boundary.

Mail entries attach to mailboxes rather than directly to users or teams.

This:

* Simplifies query patterns
* Keeps aggregation predictable
* Centralizes authorization logic

Detailed schema and invariants are defined in:

* `data_model.md`
* `data_model_decisions.md`

---

## 6. External Integrations

### Optix

* Source of truth for user and team identity.
* Identity keys treated as authoritative.

### Email Provider

* Used for weekly summary delivery.
* Failures logged but do not block processing.

### OCR Provider (Optional)

* Assists in extracting mailbox identifiers from images.
* Low-confidence results require manual confirmation.

---

## 7. Design Principles

The architecture intentionally prioritizes:

* Simplicity over distribution
* Operational clarity
* Single-instance correctness
* Low infrastructure cost
* Clear ownership boundaries

Complex infrastructure patterns (queues, distributed locks, horizontal scaling) are intentionally excluded at current scale.

---

## 8. Non-Goals

The current architecture does not attempt to provide:

* Horizontal scaling
* High-availability failover
* Multi-region deployment
* Multi-tenant enterprise isolation
* Event-driven microservices

If operating scale or constraints change, architectural revision may be required.
