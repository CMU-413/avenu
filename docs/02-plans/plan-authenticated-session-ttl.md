## Task Checklist

- Phase 1
- ☑ Add a shared authenticated-session bootstrap helper and configurable TTL.
- ☑ Route magic-link redemption and Optix bootstrap through the shared helper.
- ☑ Document the authenticated session TTL env/config values.
- Phase 2
- ☐ Add unit tests for shared permanent-session setup across all auth entry points.
- ☐ Add unit tests that prove expired authenticated session cookies no longer authenticate requests.

## Phase 1

Affected files

- `backend/config.py`: add a dedicated authenticated-session TTL config value and parse it into a validated positive duration.
- `backend/app.py`: set Flask session lifetime config from the authenticated-session TTL so permanent sessions share one source of truth.
- `backend/controllers/session_controller.py`: replace direct `session["user_id"]` assignment in magic-link redemption with a shared authenticated-session bootstrap helper.
- `backend/controllers/identity_controller.py`: replace direct `session["user_id"]` assignment in Optix bootstrap with the same shared helper.
- `backend/controllers/auth_guard.py` or `backend/controllers/common.py`: add a small shared helper that marks the session permanent and stores `user_id` without duplicating auth-source-specific logic.
- `.env.sample`: document the authenticated-session TTL env var alongside the existing auth settings.

Summary of changes per file

- `backend/config.py`: introduce a single authenticated-session TTL setting for all signed-in users with a default of 12 hours so time policy stays separate from individual auth flows.
- `backend/app.py`: wire the parsed TTL into Flask’s permanent session lifetime configuration.
- `backend/controllers/session_controller.py`: use the shared bootstrap helper after successful admin magic-link redemption.
- `backend/controllers/identity_controller.py`: use the shared bootstrap helper after successful Optix identity sync for both admins and members.
- `backend/controllers/auth_guard.py` or `backend/controllers/common.py`: keep authenticated-session setup minimal and reusable by both controllers.
- `.env.sample`: make the expected authenticated-session duration explicit in repo config.

Inline unit tests

- `backend/tests/unit/test_admin_session_auth.py`: assert magic-link redemption creates a permanent session and stores the authenticated user id through the shared path.
- `backend/tests/unit/test_identity_controller.py`: assert Optix bootstrap creates a permanent session and stores the authenticated user id through the shared path.

## Phase 2

Affected files

- `backend/tests/unit/test_admin_session_auth.py`: extend auth-session assertions to cover permanent-session flags and configured lifetime behavior.
- `backend/tests/unit/test_identity_controller.py`: extend Optix auth assertions so admin/member source differences do not bypass TTL setup.
- `backend/tests/unit/test_health_controller.py` or a new `backend/tests/unit/test_authenticated_session_ttl.py`: add focused tests around Flask session expiry enforcement without coupling to unrelated controller behavior.

Summary of changes per file

- `backend/tests/unit/test_admin_session_auth.py`: verify the magic-link path produces the same permanent session shape expected for later expiry enforcement.
- `backend/tests/unit/test_identity_controller.py`: verify the Optix path uses the identical session bootstrap behavior as magic-link redemption.
- `backend/tests/unit/test_authenticated_session_ttl.py`: exercise Flask session loading with the configured permanent lifetime so expired cookies fail to authenticate on later requests.

Inline unit tests

- `backend/tests/unit/test_admin_session_auth.py`: redeem magic-link sets `_permanent` and `user_id`.
- `backend/tests/unit/test_identity_controller.py`: Optix bootstrap sets `_permanent` and `user_id`.
- `backend/tests/unit/test_authenticated_session_ttl.py`: a permanent session cookie remains valid within the configured window and is rejected after the configured window elapses.
