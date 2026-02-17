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

````

---

## Prerequisites

You need the following installed locally:

- Docker (with Docker Compose v2)
- Node.js (only if running frontend outside Docker)
- Python 3.11+ (only if running backend outside Docker)

---

## Environment Variables

### Backend (`backend/.env`)

Create a `.env` file in `backend/`:

```env
MONGO_URI=mongodb+srv://<user>:<password>@<cluster>.mongodb.net
DB_NAME=avenu_db
ADMIN_API_KEY=your-secure-admin-api-key
````

This connects the backend to MongoDB Atlas. `ADMIN_API_KEY` is required for admin-only routes (list users, update user, delete user).

### Frontend (local dev: `frontend/.env` or `frontend/.env.local`)

For admin flows (e.g. listing users), set:

```env
VITE_ADMIN_API_KEY=your-secure-admin-api-key
```

This must match `ADMIN_API_KEY` in the backend. For Docker, pass `VITE_ADMIN_API_KEY` as an environment variable when running `docker compose up`.

---

## Running the App (Recommended: Docker)

From the repo root:

```bash
docker compose up --build
```

This will:

* build the frontend and backend images
* start both services
* wire networking automatically

### Access

* Frontend: [http://localhost:8080](http://localhost:8080)
* Backend health check: [http://localhost:5001/health](http://localhost:5001/health)

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

Runs on: [http://localhost:5001](http://localhost:5001)

---

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Runs on: [http://localhost:5173](http://localhost:5173)

## Notes

* Frontend environment variables are **build-time** and public.
* Backend environment variables are **runtime** and private.
* Docker is the source of truth for prod and CI.
* No local MongoDB instance is required.
