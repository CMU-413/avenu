# Architecture Overview

## 1. Architectural Style

The backend follows a layered architecture inside the backend container.

Layer order and dependency direction:

1. `app.py`
2. `controllers/`
3. `services/`
4. `repositories/`
5. `models/`

Allowed dependency direction:

```text
app.py -> controllers -> services -> repositories -> models
```

No cross-layer shortcuts are permitted.

External integrations are accessed from the service layer through provider abstractions.

## 2. Deployment Topology

Application containers deployed via Docker Compose:

- `frontend`
- `backend`
- `scheduler`

Production additionally includes:

- `prometheus`
- `grafana`

MongoDB is external to the Compose stack.

## 3. Communication Boundaries

Allowed communication paths:

- `frontend -> backend`
- `scheduler -> backend`
- `backend -> MongoDB`
- `backend -> Optix API`
- `backend -> email provider API`
- `backend -> SMS provider API`
- `backend -> OCR API`

Disallowed paths:

- `frontend -> MongoDB`
- `scheduler -> MongoDB`
- `frontend -> external providers`
- `scheduler -> external providers`

The backend is the only integration boundary for persistence and third-party services.

## 4. Internal Docker DNS Model

Internal service DNS names:

- `frontend`
- `backend`
- `scheduler`
- `prometheus`
- `grafana`

The scheduler reaches the backend at:

```text
http://backend:8000
```

MongoDB is reached through its external connection string over TLS when configured for Atlas.

## 5. Quality Constraint Alignment

The architecture preserves these boundaries:

- provider substitutions stay isolated behind service-layer abstractions
- notification failure isolation remains in service orchestration
- controller/service authorization boundaries are enforced through HTTP integration coverage
- shared aggregation logic remains the source of truth for member dashboard and summary behavior

## 6. Design Constraints

- No monolithic combined application container
- No internal reverse proxy embedded in application containers
- Inter-container communication uses explicit HTTP boundaries
- All third-party integrations are isolated behind the backend
- Secrets and configuration are supplied through environment variables
- MongoDB is managed externally and is not deployed inside the application stack
