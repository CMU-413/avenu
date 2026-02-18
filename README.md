# Avenu

Full-stack web application with a Vite + React frontend and a Flask + MongoDB backend.
The project is fully containerized using Docker.

---

## Repo Structure

```
├── frontend/        # Vite + React app
├── backend/         # Flask API (MongoDB Atlas)
├── docker-compose.yml
└── README.md
```

---

## Prerequisites

You need the following installed locally:

- Docker (with Docker Compose v2)
- Node.js (only if running frontend outside Docker)
- Python 3.11+ (only if running backend outside Docker)

---

## Environment Variables

### Backend (`.env` in repo root)

Create a `.env` file at the repo root (a `.env.sample` copy lives here as well):

```env
MONGO_URI=mongodb+srv://<user>:<password>@<cluster>.mongodb.net
DB_NAME=avenu_db
SECRET_KEY=replace-with-a-long-random-secret
# Optional: set true when app is served over HTTPS
SESSION_COOKIE_SECURE=false
SESSION_COOKIE_SAMESITE=Lax
SESSION_COOKIE_PARTITIONED=false
```

Notes:
- `SECRET_KEY` is required outside tests.
- For iframe/Canvas embedding, set:
  - `SESSION_COOKIE_SAMESITE=None`
  - `SESSION_COOKIE_SECURE=true`
  - optional: `SESSION_COOKIE_PARTITIONED=true`
- User sessions are created via `POST /api/session/login` with a user email.
- `POST /api/session/logout` clears the session.
- Admin routes authorize by loading `session["user_id"]` from DB and requiring `user.isAdmin == true`.

### Frontend

No admin API key env var is needed.
Browser code calls same-origin `/api` and sends cookies via `credentials: 'include'`.

---

## Running the App (Recommended: Docker)

From the repo root:

```bash
docker compose up --build
```

This will:

- build the frontend and backend images
- start both services
- proxy frontend `/api/*` requests to backend automatically

### Access

- Frontend: http://localhost:8080
- Backend health check: http://localhost:5001/health

---

## Running Without Docker

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Runs on: http://localhost:5001

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Runs on: http://localhost:5173

Vite dev server proxies `/api/*` to `http://localhost:5001`.

## Notes

- Frontend environment variables are build-time and public.
- Backend environment variables are runtime and private.
- Docker is the source of truth for prod and CI.
- No local MongoDB instance is required.
