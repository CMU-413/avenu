## Open Questions

- None.

## Task Checklist

### Phase 1
- ☑ Make `README.md` the canonical engineer entrypoint.
- ☑ Align deployment guidance with Dockge, current Compose topology, and image namespace ownership.

### Phase 2
- ☑ Remove or collapse stale duplicate docs that conflict with the canonical path.
- ☑ Align supporting config examples and architecture docs with the current deployment model.

## Phase 1

Affected files:
- `README.md`
- `docker-compose-prod.yml`

Summary of changes per file:
- `README.md`
  - Rework the doc into the primary onboarding and deployment guide.
  - Document local development, test commands, production image publishing, Dockge rollout, verification, and current service topology.
  - Call out production image registry and owner as explicit configuration instead of hardcoded maintainer-owned Docker Hub namespace.
- `docker-compose-prod.yml`
  - Replace hardcoded application image namespaces with configurable registry and owner variables so the documented rollout matches the file future maintainers will edit.

Inline unit tests:
- None; documentation and Compose configuration only.

## Phase 2

Affected files:
- `deployment.md`
- `frontend/README.md`
- `.env.sample`
- `docker-compose.yml`
- `docs/01-architecture/overview.md`

Summary of changes per file:
- `deployment.md`
  - Collapse the duplicate deployment guide into a short pointer to `README.md` so production instructions do not drift.
- `frontend/README.md`
  - Replace the default Lovable template with frontend-specific local workflow notes that match the repo.
- `.env.sample`
  - Update example values and comments to match the managed Mongo deployment model and current runtime settings.
- `docker-compose.yml`
  - Align the local backend health check with the live Flask liveness route so local Compose remains trustworthy as the documented source of truth.
- `docs/01-architecture/overview.md`
  - Remove pasted conversational framing and keep only canonical architecture content aligned with the deployed topology.

Inline unit tests:
- None; documentation-only changes.
