# Open Questions
None.

# Task Checklist
## Phase 1
- ☐ Integrate a shared magic-link engine and bind it to app-specific config plus persistent storage.
- ☐ Keep admin-only eligibility and one-time-use semantics enforced by the app’s own user/session rules.

## Phase 2
- ☐ Add backend request/redeem endpoints that use the configured magic-link engine and deliver links through the existing MS Graph email provider abstraction.
- ☐ Remove email-only session creation and add backend unit tests for token lifecycle, auth boundaries, and delivery behavior.

## Phase 3
- ☐ Replace the public email sign-in flow with a magic-link request screen and consume emailed tokens in the browser.
- ☐ Preserve query params across `/mail` → `/mail/` so emailed callback links survive nginx normalization.
- ☐ Remove frontend helpers that post raw emails to `/api/session/login`.
- ☐ Add lightweight frontend unit tests for the request flow and token-bootstrap routing.

# Phase 1: Haze Integration + Storage Contract
Affected files and changes
- `backend/requirements.txt`: add the chosen `haze` package variant so magic-link generation/verification comes from a maintained dependency rather than custom crypto/signature code.
- `backend/config.py`: add config values for Haze setup such as token TTL, signing secret/key material, and the public application base URL used to build emailed links.
- `backend/services/auth_magic_link_service.py` (new): wrap Haze configuration and expose app-level helpers for generating admin login links and redeeming them into session user ids.
- `backend/repositories/auth_magic_links_repository.py` (new): implement the persistent storage contract Haze needs so tokens survive process restarts and remain single-use.
- `backend/tests/unit/test_auth_magic_link_service.py` (new): cover Haze configuration, storage adapter behavior, expiry enforcement, and one-time-use semantics as wired in this app.

Inline unit tests
- `backend/tests/unit/test_auth_magic_link_service.py`: assert generated links use the deployed SPA base path (`https://hub.avenuworkspaces.com/mail/` in production) and verification query shape, stored token records persist the fields required by the Haze storage adapter, and consumed/expired tokens are rejected.
- `backend/tests/unit/test_auth_magic_link_service.py`: assert admin-only enforcement remains outside the library boundary so non-admin users cannot receive redeemable login links even if Haze itself can generate tokens generically.

# Phase 2: Backend Request/Redeem + Mail Delivery
Affected files and changes
- `backend/controllers/session_controller.py`: replace `POST /api/session/login` with a request endpoint that accepts an email, validates admin eligibility through app services, generates a magic link through the Haze-backed service, sends the email, and returns a non-authenticating success response; add a redeem endpoint that validates the token payload and creates the session.
- `backend/services/user_service.py`: keep admin email lookup centralized and reuse it from the magic-link auth flow.
- `backend/services/notifications/providers/factory.py`: reuse `build_email_provider()` for auth emails instead of introducing a parallel delivery path.
- `backend/services/notifications/providers/email_provider.py`: keep the existing provider contract and use it from the auth mailer flow.
- `backend/templates/emails/admin_magic_link.html` (new): render the admin login email with the sign-in URL and expiry messaging.
- `backend/tests/unit/test_admin_session_auth.py`: replace raw email-login assertions with request/redeem endpoint coverage and continued admin/member authorization checks.
- `backend/tests/unit/test_identity_controller.py`: keep `/api/optix-token` coverage intact so existing Optix bootstrap remains valid where still needed.

Inline unit tests
- `backend/tests/unit/test_admin_session_auth.py`: assert the request endpoint never authenticates by itself, returns a non-enumerating success contract for unknown/non-admin emails, and the redeem endpoint sets `session["user_id"]` only for valid unexpired tokens.
- `backend/tests/unit/test_auth_magic_link_service.py` or controller tests: assert the MS Graph-backed email provider interface is called with the rendered magic-link email subject/body.

# Phase 3: Frontend Magic-Link Request + Consumption
Affected files and changes
- `frontend/src/pages/Login.tsx`: replace direct session creation with a request form that submits an admin email for magic-link delivery and renders a neutral “check your email” confirmation state.
- `frontend/src/lib/api/routes/session.ts`: replace `sessionLogin` with request/redeem helpers for the new magic-link endpoints while keeping `sessionMe` and `sessionLogout`.
- `frontend/src/lib/api/index.ts`: export the new magic-link request/redeem helpers and remove the old login helper.
- `frontend/src/App.tsx`: on unauthenticated load, consume a magic-link token from the URL, establish the session through the new redeem endpoint, strip the token from the address bar, and route successful admins to `/admin`; keep failure handling on the login page without falling back to raw email login.
- `frontend/nginx.conf`: preserve query params when redirecting `/mail` to `/mail/` so login callbacks carrying token parameters survive the redirect before the SPA boots.
- `frontend/src/test/example.test.ts` or new auth-focused tests: cover request-form rendering, success state, and token-consumption routing.

Inline unit tests
- `frontend/src/test/...`: assert the login page posts to the magic-link request endpoint and transitions to a confirmation state instead of attempting direct session creation.
- `frontend/src/test/...`: assert token-bearing URLs trigger redemption, strip the token query param afterward, and navigate authenticated admins to `/admin`.
