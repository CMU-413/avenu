# Deployment Guide

## Topology Confirmation

Deployment topology is unchanged by backend layering refactors.
Production still runs the same four-container stack:

- `frontend`
- `backend`
- `scheduler`
- `database`

The layered architecture (`app.py -> controllers -> services -> repositories -> models`) is an internal backend code-organization change only.

## After Finishing a Commit

This project deploys via:

* Docker Hub images
* Dockge-managed Docker Compose
* nginx reverse proxy on the host
* No SSH required
* No server-side builds

All services run under a single Docker Compose stack.

Browser traffic always flows through nginx.

---

# 1. Authenticate to Docker Hub (If Needed)

```bash
docker login
```

You only need to do this once per machine.

---

# 2. Frontend Configuration (Build-Time)

Frontend configuration is build-time only.

Production values live in:

```
frontend/.env.production
```

Example:

```
VITE_BASE_PATH=/mail/
VITE_API_BASE_URL=/mail/api
```

Important:

* Do not put `VITE_*` variables in Dockge `.env`
* They will not affect already-built bundles

If you change anything in `.env.production`, you must rebuild the frontend image.

---

# 3. Build Images for Correct Architecture

The server runs `linux/amd64`.

If developing on Apple Silicon:

```bash
docker buildx create --use
```

---

## Backend

```bash
docker buildx build \
  --platform linux/amd64 \
  -t chunkitw/avenu-backend:latest \
  --push \
  ./backend
```

---

## Frontend

```bash
docker buildx build \
  --platform linux/amd64 \
  --no-cache \
  -t chunkitw/avenu-frontend:latest \
  --push \
  ./frontend
```

Use `--no-cache` if frontend env changed.

---

## Scheduler

```bash
docker buildx build \
  --platform linux/amd64 \
  -t chunkitw/avenu-scheduler:latest \
  --push \
  ./scheduler
```

---

# 4. Backend Runtime Environment (Dockge)

Backend secrets must be defined in Dockge `.env`:

Examples:

* MONGO_URI
* SECRET_KEY
* MS_GRAPH_CLIENT_SECRET
* TWILIO_ACCOUNT_SID
* TWILIO_AUTH_TOKEN
* TWILIO_PHONE_NUMBER
* SCHEDULER_INTERNAL_TOKEN
* SESSION_COOKIE_SECURE
* FRONTEND_ORIGINS

Never bake secrets into Docker images.

Frontend does not read Dockge `.env`.

---

# 5. Update Stack in Dockge

1. Open Dockge
2. Open `avenu-mail`
3. Click **Update**

Dockge will:

* Pull latest images
* Restart containers
* Preserve Mongo volume

The server never contains source code.

---

# 6. Production Routing Model

nginx on the host routes:

```
/mail       → frontend (port 18080)
/mail/api   → backend (port 18000)
```

Browser never accesses 18080 or 18000 directly in production.

All traffic flows through:

```
https://hub.avenuworkspaces.com/mail
```

If nginx routing is missing, `/mail` will not work.

---

# 7. Verification

Primary entrypoint:

```
https://hub.avenuworkspaces.com/mail
```

Do not rely on:

```
:18080
:18000
```

Those are internal integration ports.

Verify:

* Login works
* API calls succeed
* Admin flows function
* Weekly summary endpoint works

Scheduler calls backend internally via:

```
http://backend:8000
```

This is Docker-internal DNS.

---

# Deployment Flow Summary

After finishing a commit:

```
docker login (if needed)
→ docker buildx build --platform linux/amd64 --push
→ Dockge Update
→ Hard refresh browser
→ Verify via /mail
```
