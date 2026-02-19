# Open Questions
None.

# Task Checklist
## Phase 1
- ☑ Add a Microsoft Graph provider implementation under `backend/services/notifications/providers/` with OAuth2 client-credentials token acquisition, in-memory token cache, and explicit `MailProviderError`.
- ☑ Keep provider concerns isolated to provider/config modules so notifier/channel/job logic remains unchanged.
- ☑ Add focused provider unit tests for token caching, token refresh-on-expiry, and sendMail error handling.

## Phase 2
- ☑ Add provider construction/wiring helpers with a single selection rule: testing uses `ConsoleEmailProvider`, all non-testing entrypoints use `MSGraphEmailProvider`.
- ☑ Replace direct `ConsoleEmailProvider()` construction in weekly job wiring with the provider factory.
- ☑ Replace direct provider construction in admin-triggered notification routes with the same provider factory.
- ☑ Extend wiring tests to assert weekly job still continues on per-user failures (QA-R1 preserved).

## Phase 3
- ☑ Add Graph mail environment variables to `.env.sample` and Docker Compose service environment contract.
- ☑ Keep secrets out of repo by documenting placeholders only.
- ☑ Update provider exports/imports so new provider is discoverable without broad module edits.

## Phase 1: MS Graph Provider + Error Semantics
Affected files and changes
- `backend/services/notifications/providers/ms_graph_provider.py` (new): implement `MSGraphEmailProvider(EmailProvider)` with `send(to, subject, html) -> str`, internal `_get_access_token()` cache, and Graph `sendMail` call.
- `backend/services/notifications/providers/email_provider.py`: add `MailProviderError` exception type near the provider contract (or in a dedicated provider-local errors module) for normalized provider failures.
- `backend/requirements.txt`: no new dependency expected; use existing stdlib + already-installed libraries for HTTP.

Implementation details
- `MSGraphEmailProvider` constructor accepts typed config values:
  - `tenant_id`, `client_id`, `client_secret`, `sender_email`
  - optional `token_url_base`, `graph_base_url`, `timeout_seconds` for testability.
- Constructor validates required config and fails fast with `MailProviderError` on missing/blank required values.
- OAuth2 token flow:
  - POST `https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token`
  - form fields: `client_id`, `client_secret`, `scope=https://graph.microsoft.com/.default`, `grant_type=client_credentials`.
- Cache behavior:
  - store `_access_token: str | None` and `_access_token_expires_at: datetime | None`.
  - reuse token when `now < expires_at`; refresh when expired/missing.
  - subtract a small skew (for example 30-60s) from `expires_in` when computing expiry to avoid edge-expiry sends.
- sendMail behavior:
  - POST `https://graph.microsoft.com/v1.0/users/{sender_email}/sendMail`
  - payload mirrors ticket JSON and uses HTML body.
  - on non-`202`, raise `MailProviderError` containing status code + short response text.
  - on `202`, return a stable synthetic message ID (Graph sendMail response body is empty).
- Error semantics:
  - token acquisition failures (network/JSON/missing `access_token`/non-200) raise `MailProviderError`.
  - sendMail failures raise `MailProviderError`.
  - keep exceptions provider-scoped; `EmailChannel` already converts provider exceptions into channel `failed` results, preserving QA-R1 flow.

Unit tests (phase-local)
- `backend/tests/test_ms_graph_email_provider.py` (new):
  - `test_send_uses_cached_token_until_expiry`
  - `test_send_refreshes_token_after_expiry`
  - `test_send_raises_mail_provider_error_when_token_request_fails`
  - `test_send_raises_mail_provider_error_when_sendmail_not_202`
  - `test_send_returns_stable_message_id_on_202` (use provider-defined constant/id since Graph sendMail returns empty body on success).
- Use lightweight HTTP stubs via `unittest.mock.patch` around the HTTP request function; avoid integration/network tests.

## Phase 2: Provider Wiring (Weekly Job Semantics Preserved)
Affected files and changes
- `backend/services/notifications/providers/factory.py` (new): provide a single `build_email_provider(*, testing: bool = False) -> EmailProvider` function.
- `backend/scripts/run_weekly_summary_cron.py`: replace hard-coded `ConsoleEmailProvider()` with provider factory in `build_default_notifier()`.
- `backend/app.py`: replace direct provider construction in admin notification routes with same factory, keeping notifier/channel invocation unchanged.
- `backend/services/notifications/providers/__init__.py` and `backend/services/notifications/__init__.py`: export the new provider + factory.

Implementation details
- Factory selection rules:
  - test mode (`FLASK_TESTING` truthy or explicit `testing=True`) => `ConsoleEmailProvider`.
  - all non-testing modes => `MSGraphEmailProvider` (fail fast if required Graph config is missing).
- Keep wiring boundary narrow:
  - only wiring points change; no changes to `WeeklySummaryNotifier`, `EmailChannel`, `run_weekly_summary_cron_job`, or domain services.
- QA-R1 preservation:
  - per-email provider exceptions still surface as `channel.status="failed"` in `EmailChannel`.
  - cron loop continues per existing `run_weekly_summary_cron_job` exception-handling/counters.

Unit tests (phase-local)
- `backend/tests/test_weekly_summary_cron_command.py`:
  - add assertion that default notifier uses factory-selected provider (patch factory to sentinel provider).
- `backend/tests/test_admin_session_auth.py`:
  - adjust route tests to patch provider factory instead of `ConsoleEmailProvider` assumptions.
- `backend/tests/test_weekly_summary_cron_job.py`:
  - keep/extend continue-on-failure assertion to explicitly cover provider-induced notifier failure path remains non-fatal.

## Phase 3: Environment Contract + Compose
Affected files and changes
- `.env.sample`: add placeholders for Graph provider configuration.
- `docker-compose.yml`: surface Graph vars in `services.app.environment` (or ensure passthrough via `env_file` plus documented required keys).
- `README.md`: align environment documentation with `.env.sample` and required Graph keys.

Configuration additions
- `MS_GRAPH_TENANT_ID=...`
- `MS_GRAPH_CLIENT_ID=...`
- `MS_GRAPH_CLIENT_SECRET=...`
- `MS_GRAPH_SENDER_EMAIL=mail@...`

Unit tests (phase-local)
- `backend/tests/test_provider_factory.py` (new):
  - `test_factory_returns_console_provider_in_testing_mode`
  - `test_factory_returns_ms_graph_provider_when_required_env_present`
  - `test_factory_raises_mail_provider_error_when_ms_graph_env_missing`
- Keep tests pure unit tests by patching `os.environ` and asserting returned provider type only.
