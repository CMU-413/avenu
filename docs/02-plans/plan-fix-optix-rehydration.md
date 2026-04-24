# Open Questions
- None.

# Task Checklist
## Phase 1
- ☑ Preserve app-owned `notifPrefs` for existing users during Optix sync.
- ☑ Keep re-hydrating Optix-owned user fields (`fullname`, `email`, `phone`, `isAdmin`, `teamIds`) on each successful Optix login/bootstrap request to `/api/optix-token`.
- ☑ Apply change detection so unchanged Optix user data does not trigger redundant local writes.
- ☑ Add unit coverage for create-vs-update sync behavior and notification-preference ownership.

## Phase 2
- ☑ Refresh existing team names and team mailbox display names on each successful Optix login/bootstrap request to `/api/optix-token`.
- ☑ Apply change detection so unchanged Optix team/mailbox data does not trigger redundant local writes.
- ☑ Add regression coverage that Optix bootstrap still returns the correct create/update response and establishes the session.

## Phase 3
- ☑ Document the Optix login/bootstrap re-hydration rules and ownership boundaries after the sync change.
- ☑ Update any architecture or API docs that describe how Optix data populates local user/team records.

## Phase 1: User Re-hydration Ownership Boundaries
Affected files and changes
- `backend/services/identity_sync_service.py`: stop treating Avenu-managed notification preferences as Optix-owned data during login/bootstrap; pass only Optix-owned user fields into the persistence layer and keep the create/update flow explicit so existing users are re-hydrated without resetting app preferences.
- `backend/repositories/users_repository.py`: split external-identity insert defaults from external-identity update behavior so new users still receive the current default `notifPrefs`, while existing users only update Optix-owned fields (`fullname`, `email`, `phone`, `isAdmin`, `teamIds`) and retain stored Avenu preferences; build the update patch from actual field diffs so unchanged Optix payloads do not rewrite the user or mailbox rows.
- `backend/tests/unit/test_identity_sync_service.py`: add assertions that sync for existing users does not overwrite `notifPrefs`, still forwards updated phone/team data, and still reports `created=False` for update flows.

Unit tests
- `backend/tests/unit/test_identity_sync_service.py`
  - `test_sync_optix_identity_creates_new_user_with_default_notification_prefs`
  - `test_sync_optix_identity_updates_existing_user_without_overwriting_notification_prefs`
  - `test_sync_optix_identity_forwards_updated_phone_and_team_membership_for_existing_user`

## Phase 2: Other Optix-Owned Record Re-hydration
Affected files and changes
- `backend/repositories/teams_repository.py`: update `ensure_team_from_external_identity(...)` so existing teams refresh their name and mailbox display name when Optix returns different values, while unchanged payloads return without redundant writes.
- `backend/services/identity_sync_service.py`: rely on the refreshed team ensure path so every bootstrap reconciles both the user record and any referenced team records from the latest Optix payload.
- `backend/tests/unit/test_identity_sync_service.py`: extend sync coverage to assert team refresh behavior when Optix returns a renamed team.
- `backend/tests/unit/test_identity_controller.py`: keep controller-level regression coverage focused on the bootstrap contract by asserting the route still returns `200`/`201` correctly and establishes the session after the sync changes.

Unit tests
- `backend/tests/unit/test_identity_sync_service.py`
  - `test_sync_optix_identity_refreshes_existing_team_name_when_optix_payload_changes`
  - `test_sync_optix_identity_skips_team_write_when_optix_team_name_is_unchanged`
  - `test_sync_optix_identity_raises_on_optix_failure_and_does_not_write_local_state`
- `backend/tests/unit/test_identity_controller.py`
  - `test_optix_token_route_returns_updated_200`
  - `test_optix_token_route_returns_created_201`

## Phase 3: Docs Alignment
Affected files and changes
- `docs/01-architecture/api/member-api-contract.md`: update any session/bootstrap contract notes that imply Optix login overwrites Avenu-managed notification preferences or omit the re-hydration behavior for existing users.
- `docs/01-architecture/data-model.md`: clarify ownership boundaries between Optix-owned identity fields and Avenu-owned user preferences, plus note that team names/mailbox display names are refreshed from Optix during login only when changed.
- `README.md`: if the current login/bootstrap description mentions Optix sync, align it with the new change-detection and ownership behavior so local onboarding docs match the implementation.

Unit tests
- None.
