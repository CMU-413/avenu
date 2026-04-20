# Open Questions
- None. Plan assumes deletion controls live in a dedicated admin maintenance screen linked from `frontend/src/pages/admin/AdminHome.tsx`, since the current admin UI has no existing user/team management page.

# Task Checklist
## Phase 1
- ☐ Tighten and document admin-only delete behavior for users and teams in the backend HTTP layer.
- ☐ Add focused unit coverage for user delete auth and team delete auth/restrict/prune paths.

## Phase 2
- ☐ Add typed frontend delete routes for users and teams, including `pruneUsers` support for teams.
- ☐ Add an admin maintenance screen that lists users and teams, confirms destructive actions, and refreshes local state after delete.
- ☐ Link the new screen from the admin home flow and add lightweight unit tests for the new route helpers.

## Phase 1: Backend Delete Contract
Affected files and changes
- `backend/controllers/teams_controller.py`: require admin session for all `DELETE /api/teams/<team_id>` calls, keep `pruneUsers` as the only behavior switch, and preserve the current `204` success plus `409` restrict failure contract from `delete_team`.
- `backend/controllers/users_controller.py`: keep `DELETE /api/users/<user_id>` on the admin session boundary and make the delete contract explicit alongside the team delete behavior.
- `backend/services/team_service.py`: keep the controller-facing delete entrypoint limited to `prune_users` so the HTTP layer stays declarative and the existing cascade logic remains unchanged.
- `backend/services/user_service.py`: keep the controller-facing delete entrypoint as the single hard-delete path for admin use.
- `backend/tests/unit/test_admin_session_auth.py`: add route-level tests for unauthenticated and non-admin deletes on both resource types.
- `backend/tests/unit/test_user_service.py`: add focused service coverage that user delete removes the user-owned mailbox/mail cascade through the existing repository path.
- `backend/tests/unit/test_team_service.py` (new if missing): add focused service coverage for team delete restrict vs `pruneUsers=true`.

### Delete behavior
- `DELETE /api/users/<id>` stays admin-only and returns `204` on success.
- `DELETE /api/teams/<id>` becomes admin-only regardless of query params.
- `DELETE /api/teams/<id>?pruneUsers=true` keeps the existing prune behavior: remove the team id from users, then delete dependent mailbox/mail data, then delete the team.
- `DELETE /api/teams/<id>` without `pruneUsers=true` keeps the existing restrict behavior and returns `409` when users still reference the team.

### Unit tests
- `backend/tests/unit/test_admin_session_auth.py`: user delete returns `401` without session and `403` for non-admin session.
- `backend/tests/unit/test_admin_session_auth.py`: team delete returns `401` without session and `403` for non-admin session with and without `pruneUsers=true`.
- `backend/tests/unit/test_user_service.py`: deleting a user removes owned mailbox/mail records before deleting the user document.
- `backend/tests/unit/test_team_service.py`: deleting a referenced team without prune raises `409`; deleting with prune removes memberships and dependent mailbox/mail artifacts.

## Phase 2: Admin Maintenance UI + API Wiring
Affected files and changes
- `frontend/src/lib/api/routes/users.ts`: add `deleteUser(userId: string)` using the existing `apiFetch` helper and `DELETE /users/:id`.
- `frontend/src/lib/api/routes/teams.ts`: add `deleteTeam(teamId: string, options?: { pruneUsers?: boolean })` and encode the `pruneUsers=true` query only when requested.
- `frontend/src/lib/api/contracts/types.ts`: keep existing `ApiUser` and `ApiTeam` types as the list/delete source of truth; add no new response models unless the UI needs a small local options type.
- `frontend/src/pages/admin/AdminUsersTeams.tsx` (new): load users and teams together, split display by resource type, expose destructive actions behind the shared confirmation dialog, and refresh local lists after successful deletes.
- `frontend/src/pages/admin/AdminHome.tsx`: add navigation to the new maintenance screen.
- `frontend/src/App.tsx`: register the new admin route behind the existing admin session gate.
- `frontend/src/pages/admin/SearchMailbox.tsx`: if this screen remains the place admins discover teams/users operationally, link through to the maintenance screen rather than mixing delete controls into the mailbox recording flow.
- `frontend/src/lib/api/routes/users.test.ts` and `frontend/src/lib/api/routes/teams.test.ts` (or the repo’s equivalent frontend unit-test location): add small unit tests around URL/method construction and `pruneUsers` query encoding.

### UI behavior
- Show non-admin users in one list and teams in a second list so destructive actions stay scoped and readable.
- Use the existing confirmation dialog provider for all deletes.
- User delete confirms permanent removal of the user plus owned mailbox/mail data.
- Team delete exposes a default delete action that succeeds only when the team has no members.
- Team delete exposes a separate prune-and-delete action for the existing `pruneUsers=true` path when the admin confirms member associations should be removed first.
- After a successful delete, remove the item from local state or refetch the lists so the page remains consistent without a full reload.
- Reuse the existing unauthorized handling pattern: toast the error, and on `401` or `403` clear session state and redirect to `/`.

### Unit tests
- `frontend/src/lib/api/routes/users.test.ts`: `deleteUser` issues `DELETE` to `/users/:id`.
- `frontend/src/lib/api/routes/teams.test.ts`: `deleteTeam` issues `DELETE` to `/teams/:id` and appends `?pruneUsers=true` only when requested.
