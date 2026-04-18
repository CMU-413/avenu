- Open Questions: None.

- ☑ Phase 1: Update admin Teams delete/prune copy in the UI while keeping `pruneUsers` API usage unchanged.
- ☑ Phase 2: Add lightweight unit coverage for the renamed user-facing labels.

## Phase 1

- Affected files:
  - `frontend/src/pages/admin/AdminUsersTeams.tsx`
- Changes:
  - Replace every user-facing team-prune label, dialog title, dialog confirm button label, loading state, and restrict-path guidance message from `Prune` wording to `Remove Members & Delete`.
  - Preserve the existing `pruneUsers` boolean flow, request construction, and delete behavior.
- Inline unit tests:
  - None.

## Phase 2

- Affected files:
  - `frontend/src/test/admin-users-teams.test.tsx`
- Changes:
  - Render the admin Teams screen with mocked data/hooks and assert the `Remove Members & Delete` button is shown for teams with members.
  - Trigger the prune path and assert the confirm dialog receives the renamed title and confirm label while the backend call still uses `{ pruneUsers: true }`.
- Inline unit tests:
  - `frontend/src/test/admin-users-teams.test.tsx`
