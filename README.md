# Avenu

Avenu is a full-stack mail management application with:

- a React SPA in `frontend/`
- a Flask API in `backend/`
- a scheduler worker in `scheduler/`
- a managed external MongoDB database

Docker Compose is the source of truth for local development and production topology.

## Start Here

For a new engineer, the canonical path is:

1. Read this `README.md` for setup, testing, deployment, and rollout.
2. Read [docs/01-architecture/overview.md](docs/01-architecture/overview.md) for service boundaries.
3. Read the API contracts in [docs/01-architecture/api/member-api-contract.md](docs/01-architecture/api/member-api-contract.md) and [docs/01-architecture/api/admin-notification-api-contract.md](docs/01-architecture/api/admin-notification-api-contract.md).
4. Use [docs/00-drivers/04-quality-assurance.md](docs/00-drivers/04-quality-assurance.md) to understand the test boundaries that must stay intact.

`docs/02-plans/` contains implementation plans and historical change plans. It is not the canonical source for current runtime behavior.

## System Topology

Runtime services:

- `frontend`: serves the SPA and proxies `/mail/api/*` to the backend
- `backend`: owns business logic, persistence, auth, metrics, and third-party integrations
- `scheduler`: internal backend client for recurring jobs
- `prometheus`: scrapes backend metrics in production
- `grafana`: reads Prometheus data in production

Data storage is external MongoDB. The database is not part of the Compose stack.

Allowed communication paths:

- `frontend -> backend`
- `scheduler -> backend`
- `backend -> MongoDB`
- `backend -> Optix`
- `backend -> Microsoft Graph`
- `backend -> Twilio`

Disallowed paths:

- `frontend -> MongoDB`
- `scheduler -> MongoDB`
- `frontend -> external providers`
- `scheduler -> external providers`

## Repo Layout

```text
.
├── backend/
├── frontend/
├── scheduler/
├── docs/
├── docker-compose.yml
├── docker-compose-prod.yml
└── .env.sample
```

## Environment Configuration

Copy `.env.sample` to `.env` for local development. Production uses a Dockge-managed `.env` for runtime variables.

Backend runtime variables:

- `MONGO_URI`
- `DB_NAME`
- `SECRET_KEY`
- `FRONTEND_ORIGINS`
- `SCHEDULER_INTERNAL_TOKEN`
- `SESSION_COOKIE_NAME`
- `SESSION_COOKIE_SAMESITE`
- `SESSION_COOKIE_SECURE`
- optional `SESSION_COOKIE_PARTITIONED`
- `AUTHENTICATED_SESSION_TTL_SECONDS`
- `AUTH_MAGIC_LINK_BASE_URL`
- `AUTH_MAGIC_LINK_PATH`
- `AUTH_MAGIC_LINK_EXPIRY_SECONDS`
- optional `AUTH_MAGIC_LINK_SECRET`
- `LOGIN_RATE_LIMIT_IP_WINDOW_SECONDS`
- `LOGIN_RATE_LIMIT_IP_MAX_ATTEMPTS`
- `LOGIN_RATE_LIMIT_EMAIL_WINDOW_SECONDS`
- `LOGIN_RATE_LIMIT_EMAIL_MAX_ATTEMPTS`

Notification provider variables for non-test environments:

- `MS_GRAPH_TENANT_ID`
- `MS_GRAPH_CLIENT_ID`
- `MS_GRAPH_CLIENT_SECRET`
- `MS_GRAPH_SENDER_EMAIL`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_PHONE_NUMBER`

Frontend build-time variables:

- `VITE_BASE_PATH` default `/mail/`
- `VITE_API_BASE_URL` default `/mail/api`

Scheduler runtime variables:

- `BACKEND_API_URL` default `http://backend:8000`
- `SCHEDULER_INTERNAL_TOKEN`
- `SCHEDULER_CRON`
- `SCHEDULER_TIMEZONE`
- `SCHEDULER_TICK_SECONDS`

Production-only Compose conveniences:

- `IMAGE_NAMESPACE` controls the Docker Hub namespace used by `docker-compose-prod.yml`
- `PROMETHEUS_DATA_DIR`, `PROMETHEUS_CONFIG_DIR`, and `GRAFANA_DATA_DIR` map host storage into containers
- `GRAFANA_ROOT_URL` must match the public subpath used by nginx
- `GRAFANA_ADMIN_PASSWORD` sets the Grafana admin password

## Authentication Notes

Production assumes authentication is initiated upstream through Optix or the embedding context, while the backend also supports admin magic-link login.

Important settings:

- local magic-link base URL: `http://localhost:8080/mail`
- production magic-link base URL: `https://hub.avenuworkspaces.com/mail`
- `AUTH_MAGIC_LINK_PATH` must stay aligned with the frontend nginx redirect behavior so query parameters survive `/mail -> /mail/`

Authenticated Flask sessions default to 12 hours via `AUTHENTICATED_SESSION_TTL_SECONDS`. Magic links are separate one-time credentials with their own TTL via `AUTH_MAGIC_LINK_EXPIRY_SECONDS`.

## Local Development

### Compose

From the repo root:

```bash
docker compose up --build
```

Local endpoints:

- app: [http://localhost:8080/mail](http://localhost:8080/mail)
- backend liveness: [http://localhost:8000/api/health](http://localhost:8000/api/health)

### Without Compose

Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Scheduler:

```bash
cd scheduler
SCHEDULER_INTERNAL_TOKEN=<token> BACKEND_API_URL=http://localhost:8000 python main.py
```

## Tests

Backend unit tests:

```bash
cd backend
coverage run -m unittest discover -s tests/unit -p "test_*.py" -t .
coverage report --fail-under=75
```

Backend integration tests:

Prerequisite: local Mongo reachable at `localhost:27017` and a dedicated test database named `avenu_db_dev`.

```bash
cd backend
RUN_MONGO_INTEGRATION=1 \
MONGO_URI=mongodb://localhost:27017/avenu_db_dev \
DB_NAME=avenu_db_dev \
FLASK_TESTING=true \
python -m unittest discover -s tests/integration -t .
```

Scheduler tests:

```bash
cd scheduler
python -m unittest discover tests
```

Frontend checks:

```bash
cd frontend
npm install
npm run lint
npx tsc --noEmit
npm run build
```

## CI and Image Publishing

GitHub Actions runs:

- backend unit tests
- backend integration tests
- scheduler tests
- frontend lint, type-check, and build

On `main`, CI builds and pushes application images to Docker Hub.

Current implementation detail:

- CI currently pushes to the `chunkitw` namespace in [`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml).
- Production Compose now supports `IMAGE_NAMESPACE`, but CI still needs to be updated manually if image ownership moves to another account or organization.

Required GitHub secrets:

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`

## Production Deployment and Dockge Rollout

`README.md` is the canonical deployment guide. `deployment.md` only points back here to avoid drift.

### Production Topology

Production uses:

- Docker Hub images for `frontend`, `backend`, and `scheduler`
- a Dockge-managed `docker-compose-prod.yml` stack
- host nginx routing public traffic to the internal container ports
- external MongoDB
- Prometheus and Grafana as part of the production Compose stack

### Before First Rollout

1. Set the Docker Hub namespace in Dockge `.env` with `IMAGE_NAMESPACE`.
2. Set all backend and scheduler runtime secrets in Dockge `.env`.
3. Set host storage paths for:
   - `PROMETHEUS_DATA_DIR`
   - `PROMETHEUS_CONFIG_DIR`
   - `GRAFANA_DATA_DIR`
4. Confirm the Prometheus config exists at the chosen config directory and is compatible with the mounted path.
5. Confirm nginx routes:
   - `/mail -> frontend :18080`
   - `/mail/api -> backend :18000`
   - `/mail/grafana -> frontend proxy -> grafana`

### Frontend Build-Time Rules

Frontend `VITE_*` variables are build-time only.

- Put production values in `frontend/.env.production` before building the frontend image.
- Do not expect Dockge runtime `.env` changes to alter an already-built frontend bundle.
- Rebuild the frontend image whenever build-time values change.

### Publishing Images

If building manually, publish `linux/amd64` images:

Backend:

```bash
docker buildx build --platform linux/amd64 -t <namespace>/avenu-backend:latest --push ./backend
```

Frontend:

```bash
docker buildx build --platform linux/amd64 -t <namespace>/avenu-frontend:latest --push ./frontend
```

Scheduler:

```bash
docker buildx build --platform linux/amd64 -t <namespace>/avenu-scheduler:latest --push ./scheduler
```

Replace `<namespace>` with the Docker Hub account or org that owns the images. The sample production Compose defaults to `chunkitw`, but future maintainers should treat that as an overrideable placeholder, not a permanent constant.

### Dockge Update Flow

After images are published:

1. Open the `avenu-mail` stack in Dockge.
2. Confirm the stack uses the expected `IMAGE_NAMESPACE` and runtime `.env`.
3. Click `Update` so Dockge pulls the latest images and restarts the services.
4. Hard refresh the browser after the rollout if frontend assets changed.

### Rollback

The current production Compose uses `:latest` tags. That keeps rollout simple but makes rollback dependent on retagging or editing image references in Dockge. If maintainers need deterministic rollback, use immutable tags such as `sha-<git-sha>` and update the stack explicitly.

### Post-Deploy Verification

Verify through the public path, not the container ports:

- app loads at [https://hub.avenuworkspaces.com/mail](https://hub.avenuworkspaces.com/mail)
- login works
- member API calls succeed
- admin mail-request flows succeed
- backend liveness responds at `/mail/api/health` through nginx
- scheduler can still reach `http://backend:8000` internally
- Grafana loads at `/mail/grafana/`

Do not treat `:18080` or `:18000` as public entrypoints.
