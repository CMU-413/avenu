# Open Questions
None.

# Task Checklist
## Phase 1
- ☑ Rewrite the Vite dev proxy path for `/mail/api` so local frontend requests reach backend `/api` routes.
- ☑ Leave Docker/nginx production proxy behavior unchanged.

## Phase 1: Vite Dev Proxy Path Rewrite
Affected files and changes
- `frontend/vite.config.ts`: add a rewrite for the `/mail/api` dev proxy from `/mail/api/...` to `/api/...` before forwarding to the local backend.
