# Open Questions
- None.

# Locked Decisions
- `main` publishes to GHCR only; Docker Hub is not retained as a transition publish target.
- Production image configuration uses explicit `IMAGE_REGISTRY` and `IMAGE_OWNER` variables.

# Task Checklist
## Phase 1
- ☑ Switch CI publishing from Docker Hub auth and tags to GHCR auth and tags.
- ☑ Preserve `latest` and `sha-<git-sha>` tags for each published service image.
- ☑ Remove Docker Hub secret requirements from the documented CI contract.

## Phase 2
- ☑ Rework production image references to point at GHCR-owned images.
- ☑ Align sample env/config variables with the chosen image-reference model.
- ☑ Document any required GHCR package visibility or host pull-auth setup for Dockge.

## Phase 3
- ☑ Remove Docker Hub as the canonical registry from deployment and publishing docs.
- ☑ Either remove stale Docker Hub references or mark intentional temporary transition behavior explicitly.

## Phase 1

Affected files:
- `.github/workflows/ci-cd.yml`
- `README.md`

Summary of changes per file:
- `.github/workflows/ci-cd.yml`
  - Add `packages: write` permission for the publish job path.
  - Replace Docker Hub login with GHCR login using `${{ github.actor }}` and `${{ secrets.GITHUB_TOKEN }}`.
  - Publish changed service images to `ghcr.io/cmu-413/avenu-backend`, `ghcr.io/cmu-413/avenu-frontend`, and `ghcr.io/cmu-413/avenu-scheduler`.
  - Preserve both `latest` and `sha-${{ github.sha }}` tags for each service.
- `README.md`
  - Update the CI publishing section to describe GHCR as the default registry and remove Docker Hub credential setup from the required GitHub secrets list.

Inline unit tests:
- None; workflow and documentation changes only.

## Phase 2

Affected files:
- `docker-compose-prod.yml`
- `.env.sample`
- `README.md`

Summary of changes per file:
- `docker-compose-prod.yml`
  - Replace Docker Hub image defaults with GHCR image references for `frontend`, `backend`, and `scheduler`.
  - Switch the Compose image references to `IMAGE_REGISTRY` and `IMAGE_OWNER` so registry changes do not require string-shape changes.
- `.env.sample`
  - Replace `IMAGE_NAMESPACE=chunkitw` with `IMAGE_REGISTRY=ghcr.io` and `IMAGE_OWNER=cmu-413`.
  - Add only the minimal comments needed to show how production hosts should point Dockge at `ghcr.io/cmu-413`.
- `README.md`
  - Update production rollout instructions, manual publish examples, and rollback guidance to use GHCR image names and tags.
  - Document the production requirement for package visibility and any needed `docker login ghcr.io` or token setup on pull hosts if images are not public.

Inline unit tests:
- None; Compose, env example, and documentation changes only.

## Phase 3

Affected files:
- `README.md`
- `docs/02-plans/plan-docs-readme-deployment-alignment.md`

Summary of changes per file:
- `README.md`
  - Remove Docker Hub as the canonical publish and deploy path.
  - Make GHCR-only publishing explicit and remove temporary-transition language that implies Docker Hub remains active.
- `docs/02-plans/plan-docs-readme-deployment-alignment.md`
  - Update the stale planning reference that currently describes Docker Hub namespace ownership so the plan set stays aligned with GHCR as the target registry.

Inline unit tests:
- None; documentation-only changes.
