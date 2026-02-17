# Open Questions
None.

# Locked Decisions
- Session login is account-based; backend stores `session["user_id"]`.
- Admin authorization is role-based from persisted user data (`user.isAdmin`), loaded from DB per protected request.
- Session lifetime is browser-session only (non-permanent).
- `/health` remains unprefixed.

# Task Checklist
## Phase 1
- ☑ Replace API-key admin auth with cookie-session account auth (`/api/session/login`, `/api/session/logout`, `require_admin_session`).
- ☑ Add backend session/cookie config from env (`SECRET_KEY`, secure/httpOnly/sameSite behavior) and move API routes behind `/api` prefix.
- ☑ Add focused backend unit tests for login/logout/session gate behavior and unauthorized access.

## Phase 2
- ☑ Remove `VITE_ADMIN_API_KEY` usage and add admin login flow in frontend using cookie credentials.
- ☑ Standardize browser API calls to relative `/api` with `credentials: 'include'`.
- ☑ Keep frontend auth/network logic small and declarative without introducing a component-heavy test harness in this phase.

## Phase 3
- ☑ Add `/api` reverse-proxy wiring in Vite dev server and nginx runtime config.
- ☑ Update container/build config and docs to remove API-key envs and document session-based admin auth.
- ☑ Keep proxy behavior config-only (no integration tests).

## Phase 1: Backend Admin Session Auth + API Prefix
Affected files and changes
- `backend/app.py`: introduce an `/api`-prefixed route grouping (Blueprint or equivalent), add `POST /api/session/login` + `POST /api/session/logout`, switch admin-protected routes to session-based decorator, and remove API-key decorator imports/usages.
- `backend/auth.py`: replace API-key auth with session account lookup + role guard (`require_admin_session`, `ensure_admin_session`) that loads current user from DB and checks `isAdmin`.
- `backend/services/auth.py`: removed; admin auth logic is consolidated in `backend/auth.py`.
- `backend/config.py`: remove `ADMIN_API_KEY`; keep session config env (`SECRET_KEY`, optional `SESSION_COOKIE_SECURE`) and DB/index config.
- `backend/requirements.txt`: remove `Flask-Cors` if no longer needed after same-origin `/api` proxying.
- `backend/tests/test_admin_session_auth.py` (new): add focused Flask test-client coverage for session auth flows.

### Route and auth behavior
- Add `POST /api/session/login` request body contract:
  - `{ "email": string }`
- Resolve user by normalized email and on success set `session['user_id'] = <user id>`.
- Add `POST /api/session/logout` that clears session user id (`session.pop('user_id', None)`) and returns `204`.
- Replace every admin gate currently using API key with `@require_admin_session`:
  - `GET /api/users`, `PATCH /api/users/<id>`, `DELETE /api/users/<id>`, and admin-only `pruneUsers=true` path.
- Return `401 {"error":"unauthorized"}` when session is missing/invalid.
- Return `403 {"error":"forbidden"}` when session user exists but `isAdmin` is not true.

### Session configuration
- Configure Flask session settings in `create_app()` from env/config:
  - `SECRET_KEY` required in non-test runtime.
  - `SESSION_COOKIE_HTTPONLY = True`.
  - `SESSION_COOKIE_SAMESITE = 'Lax'`.
  - `SESSION_COOKIE_SECURE` driven by environment (`False` for local HTTP dev; `True` when deployed behind HTTPS).
- Keep session state minimal: only boolean admin flag (and optional username string for observability if desired).

### Unit tests (phase-local)
- `POST /api/session/login` with valid account sets `session["user_id"]`.
- Unknown login account returns `401`.
- Protected admin route without session returns `401`.
- Protected admin route with non-admin session returns `403`.
- Protected admin route with admin session succeeds.
- `POST /api/session/logout` clears session and subsequent protected call returns `401`.
- `DELETE /api/teams/<id>?pruneUsers=true` requires admin session and returns `403` for non-admin users.

## Phase 2: Frontend Cookie Auth Flow + Relative API Calls
Affected files and changes
- `frontend/src/App.tsx`: removed `VITE_ADMIN_API_KEY` header auth, added account login form posting to `/api/session/login`, added logout via `/api/session/logout`, and ensured API calls use relative `/api` with `credentials: 'include'`.
- `frontend/src/AdminMailIntakeForm.tsx`: replaced absolute backend URL with `/api` base and included credentials on request.
- `frontend/src` (optional new file `api.ts`): centralize `apiFetch(path, init)` helper that always applies `credentials: 'include'` and JSON defaults to avoid duplicated per-call config.

### Frontend behavior
- Add a minimal session login UI (route-level or inline) that posts account email to `/api/session/login`.
- On successful login, allow admin actions (for current UI: fetch users).
- On `401` from admin endpoints, reset local admin state and prompt login.
- Remove all `VITE_ADMIN_API_KEY` references from frontend runtime/build logic.
- Set `API_BASE_URL = '/api'` in browser code (no `http://backend:5001` or `localhost:5001` in shipped frontend code).

### Unit tests (phase-local)
- If lightweight unit-test setup is added (Vitest + RTL), add focused tests for helper/login behavior:
  - `apiFetch` always sends `credentials: 'include'`.
  - Login submit posts to `/api/session/login` with expected payload.
  - `401` response path transitions UI back to logged-out state.
- If test harness is intentionally deferred, keep logic in small pure helpers to make later unit coverage straightforward without component-heavy tests.

## Phase 3: /api Reverse Proxy + Config/Docs Cleanup
Affected files and changes
- `frontend/vite.config.ts`: add dev server proxy mapping `/api` -> backend (`http://localhost:5001`) with cookie-preserving proxy defaults.
- `frontend/nginx.conf`: add `/api` location block proxying to backend container service (`http://backend:5001`) while keeping SPA fallback for `/`.
- `docker-compose.yml`: remove `VITE_ADMIN_API_KEY` build arg/env; simplify frontend build args to no backend host coupling in browser bundle.
- `frontend/Dockerfile`: remove `VITE_ADMIN_API_KEY` and unnecessary API host build args now that browser code uses relative `/api`.
- `README.md`: replace API-key instructions with session-auth env config (`SECRET_KEY`, admin credentials), and document `/api` proxy behavior in dev/docker.
- `backend/app.py` and `backend/requirements.txt`: removed Flask-Cors wiring/dependency now that browser traffic is same-origin via `/api` proxy.

### Proxy/network behavior
- Browser always calls same-origin `/api/*`.
- Vite dev server forwards `/api/*` to Flask backend for local development.
- Nginx serving built frontend forwards `/api/*` to backend service in Docker.
- With same-origin requests, remove/avoid broad CORS setup in backend unless a non-browser client explicitly requires cross-origin access.

### Unit tests (phase-local)
- Backend unit test to assert `/api` prefix routing for session endpoints (e.g., `/api/session/login` exists; legacy `/api/admin/login` path is absent).
- No integration proxy tests; keep proxy behavior declarative in config and validated by static config review/lint where available.
