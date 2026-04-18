# Frontend

The frontend is a Vite React SPA served behind nginx at `/mail/`.

## Local Development

```bash
npm install
npm run dev
```

Default local URL:

- [http://localhost:8080/mail](http://localhost:8080/mail)

The frontend expects:

- `VITE_BASE_PATH=/mail/`
- `VITE_API_BASE_URL=/mail/api`

Local development proxies `/mail/api/*` to the backend at `http://localhost:8000/api/*`.

## Quality Checks

```bash
npm run lint
npx tsc --noEmit
npm run build
```

## Deployment Notes

- Frontend `VITE_*` variables are build-time only.
- Production values belong in `frontend/.env.production` before the image is built.
- Dockge runtime `.env` changes do not rewrite an already-built frontend bundle.
