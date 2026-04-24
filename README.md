# Avenu

A full-stack mail management app for Avenu coworking spaces.

Core application services:

- `frontend` — React SPA
- `backend` — Flask API and business logic
- `scheduler` — internal job runner

MongoDB is external and not part of the Compose stack.

## Local setup

1. Copy `.env.sample` to `.env`
2. Fill in the required values
3. Start the stack from the repo root

```bash
docker compose up --build
````

Local endpoints:

* App: `http://localhost:8080/mail`
* Backend health: `http://localhost:8000/api/health`

### Manual startup

Backend:

```bash id="5rj7u1"
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Frontend:

```bash id="9k2p7v"
cd frontend
npm install
npm run dev
```

Scheduler:

```bash id="8x1n6q"
cd scheduler
SCHEDULER_INTERNAL_TOKEN=<token> BACKEND_API_URL=http://localhost:8000 python main.py
```

## Deployment

Production uses:

* GHCR for container images
* Dockge to manage the production Compose stack
* nginx on the host for public routing
* external MongoDB
* Prometheus and Grafana in the production stack for monitoring

Important deployment facts:

* `frontend`, `backend`, and `scheduler` are the deployable app services
* frontend config is build-time
* backend and scheduler config are runtime
* scheduler reaches backend internally at `http://backend:8000`
* runtime secrets/config are managed outside the images
* auth pathing must stay aligned with the deployed `/mail` base path

Public routes:

* `/mail` → frontend
* `/mail/api` → backend
* `/mail/grafana` → Grafana

Typical deploy flow:

1. Publish updated images to GHCR
2. Ensure Dockge runtime config is correct
3. Update or restart the production stack in Dockge
4. Verify through the public URL

Post-deploy checks:

* app loads
* login works
* backend health responds
* admin/member flows work
* scheduler can still hit backend internally
* Grafana still loads

## Optix Login Bootstrap

`POST /api/optix-token` is the Optix-authenticated login/bootstrap path.

On each successful Optix login:

* refresh Optix-owned user fields only when the incoming values changed
* refresh existing team names and team mailbox display names only when the incoming values changed
* preserve Avenu-owned user preferences such as `notifPrefs`

This keeps local identity data current without rewriting unchanged rows on every login.

## Learn more

* Architecture overview: `docs/01-architecture/overview.md`
* API contracts: `docs/01-architecture/api/`
* Testing strategy: `docs/00-drivers/04-quality-assurance.md`
* Deployment details: `docs/01-architecture/deployment.md`
* Product and requirements docs: `docs/`
