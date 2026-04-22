# Open Questions
- None.

# Task Checklist
## Phase 1
- ☑ Make the workflow publish matrix include all GHCR services independent of path-change detection.
- ☑ Keep selective build/test matrices driven by detected service changes.

## Phase 2
- ☑ Allow the deploy job to run on `main` pushes when upstream jobs are skipped for no-op changes.
- ☑ Preserve the guard that prevents image pushes when required upstream jobs fail.

## Phase 1

Affected files:
- `.github/workflows/ci-cd.yml`

Summary of changes per file:
- `.github/workflows/ci-cd.yml`
  - Add a deploy publish matrix that always includes `backend`, `frontend`, and `scheduler`.
  - Keep the existing change-detected build matrix for selective build/test execution.

Inline unit tests:
- None; workflow-only change.

## Phase 2

Affected files:
- `.github/workflows/ci-cd.yml`

Summary of changes per file:
- `.github/workflows/ci-cd.yml`
  - Update the deploy job condition so `main` pushes still publish GHCR images when build/test jobs are skipped due to no detected service changes.
  - Keep deploy blocked when `build` or `backend-integration` actually fail or are cancelled.

Inline unit tests:
- None; workflow-only change.
