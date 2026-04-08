# Open Questions
None.

# Task Checklist
## Phase 1
- ☐ Add a shared login-attempt rate-limit store and policy config for per-IP and per-email windows.
- ☐ Keep limit state independent from controller logic so `POST /api/session/login` can be gated at the request layer.

## Phase 2
- ☐ Apply the rate limiter to the session login request path while preserving the existing non-enumerating `202 {"status":"ok"}` contract for throttled requests.
- ☐ Log throttled requests and extend backend unit tests for per-IP, per-email, and non-throttled login behavior.

# Phase 1: Shared Login Rate-Limit Primitives
Affected files and changes
- `backend/config.py`: add tunable login rate-limit settings for the per-IP minute window, per-email multi-minute window, and any shared defaults needed by the request-layer limiter; add a dedicated Mongo collection plus TTL/lookup indexes for expiring attempt buckets automatically.
- `backend/repositories/login_rate_limit_repository.py` (new): implement the minimal persistence boundary for recording and counting normalized login attempts by scope (`ip`, `email`) using atomic upserts against time-bucketed documents so limits stay consistent across app instances.
- `backend/controllers/session_rate_limit.py` (new): define the request-layer limiter entrypoint that extracts the forwarded client IP, normalizes the submitted email, checks both scopes through the repository, and returns a neutral throttle decision object rather than mixing persistence into the controller.

Inline unit tests
- `backend/tests/unit/test_login_rate_limit_repository.py` (new): assert per-scope attempt increments are atomic, window boundaries reset counts cleanly, and expired buckets are isolated by scope/key.
- `backend/tests/unit/test_admin_session_auth.py`: cover limiter decisions that should allow the request path to proceed when both counters are below threshold.

# Phase 2: Session Login Middleware + Logging
Affected files and changes
- `backend/controllers/session_controller.py`: attach a `before_request` gate for the login endpoint that invokes the shared limiter before email delivery runs, short-circuits throttled requests with the existing `202 {"status":"ok"}` payload, and logs throttle events without leaking whether the email belongs to an admin account.
- `backend/app.py`: keep app-level error handling unchanged while ensuring the request context exposes the proxied client IP that the limiter consumes.
- `backend/tests/unit/test_admin_session_auth.py`: extend login-route coverage for per-IP throttling, per-email throttling across repeated requests, and the guarantee that throttled requests do not call `AuthMagicLinkService` or the email provider.

Inline unit tests
- `backend/tests/unit/test_admin_session_auth.py`: assert repeated requests from one IP are throttled after the configured threshold but still return `202 {"status":"ok"}` with no session mutation.
- `backend/tests/unit/test_admin_session_auth.py`: assert repeated requests for one normalized email throttle even when the response stays non-enumerating and even when the email is not an eligible admin.
- `backend/tests/unit/test_admin_session_auth.py`: assert non-throttled admin requests still send the magic-link email, and throttled requests emit a warning log entry with scope metadata but no account-existence signal.
