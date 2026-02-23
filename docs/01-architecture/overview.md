Good catch. This doc is now inconsistent with reality in two places:

* Database is no longer a container.
* Internal Docker DNS list still includes `database`.

Below is the corrected and tightened `overview.md`, aligned with:

* MongoDB Atlas as external managed database
* 3-container Compose stack
* Updated communication boundaries
* Accurate internal DNS model

---

# Architecture Overview

## 1. Architectural Style

The Avenu backend follows a layered architecture inside the backend container.

Layer order and dependency direction:

1. `app.py` — composition root
2. `controllers/` — HTTP boundary
3. `services/` — use-case orchestration
4. `repositories/` — persistence boundary
5. `models/` — domain entities and builders

Allowed dependency direction is strictly one-way:

```
app.py -> controllers -> services -> repositories -> models
```

No cross-layer shortcuts are permitted.

All external integrations are accessed from the service layer via provider abstractions.

---

## 2. Deployment Topology

Runtime topology consists of three application containers deployed via Docker Compose:

* Frontend container (`frontend`)
* Backend container (`backend`)
* Scheduler container (`scheduler`)

The database is not containerized within the Compose stack.
Persistence is provided by a managed external MongoDB Atlas instance.

Backend layering is internal to the backend container and does not alter Docker topology.

---

## 3. Communication Boundaries

Allowed communication paths:

* Frontend → Backend (JSON/HTTP)
* Scheduler → Backend (HTTP via Docker DNS)
* Backend → MongoDB Atlas (MongoDB/TLS)
* Backend → Optix API (JSON/HTTPS)
* Backend → Email Provider API (HTTPS)
* Backend → SMS Provider API (HTTPS)
* Backend → OCR API (JSON/HTTPS)

Disallowed paths:

* Frontend → MongoDB
* Scheduler → MongoDB
* Frontend → External providers
* Scheduler → External providers

The backend is the sole integration boundary for persistence and third-party services.

---

## 4. Internal Docker DNS Model

Within the Docker Compose network, service DNS names are:

* `frontend`
* `backend`
* `scheduler`

The scheduler reaches the backend via:

```
http://backend:8000
```

MongoDB Atlas is external and is accessed via its managed cloud endpoint over TLS.

---

## 5. Quality Constraint Alignment

QA-M1 remains satisfied:

External provider replacements such as OCR, email, or SMS are isolated to provider abstractions and service wiring. No modifications are required to:

* Repository layer
* Domain models
* Aggregation logic
* HTTP controller contracts

Notification failure isolation and cross-channel aggregation integrity remain enforced at the service layer.

---

## 6. Design Constraints

* No monolithic combined application container.
* No internal reverse proxy embedded in application containers.
* Inter-container communication uses explicit HTTP boundaries.
* All third-party integrations are isolated behind the backend.
* Secrets and configuration are supplied via environment variables.
* The database is a managed external service and is not deployed within the application stack.
