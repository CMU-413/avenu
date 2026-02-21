# Open Questions
None.

# Locked Decisions
- Scope is backend-only; no frontend/UI/preference API changes.
- Keep existing notification status semantics (`sent`/`skipped`/`failed`) and channel result shape.
- Keep failure isolation behavior: one channel/provider failure must not stop other channel attempts or cron/user loop progression.
- SMS channel wiring is mandatory in backend notifier construction; Twilio env vars are required for non-testing runtime.
- Weekly-summary eligibility is intent-level and decoupled from any single channel. For each intent-eligible user, dispatch is attempted only on channels enabled in that user’s `notifPrefs`.
- Channel preference mapping is explicit (`"email"` -> EmailChannel, `"text"` -> SMSChannel); no channel preference implies eligibility for any other channel.
- Top-level notifier status derivation for attempted dispatch:
  - `sent` when any channel result is `sent`
  - `failed` when at least one channel failed and none sent
  - `skipped` when all channel results are `skipped`

# Task Checklist
## Phase 1
- ☑ Add SMS provider abstraction and Twilio provider implementation under `backend/services/notifications/providers/`.
- ☑ Add `SMSChannel` with template rendering, phone-required skip behavior, and channel-result normalization.
- ☑ Extend notification payload/result typing for SMS-specific skip semantics without changing existing email behavior.
- ☑ Make SMS provider return a typed result object (not raw string) for extensibility.
- ☑ Add unit tests for provider/channel success, skip, and failure branches.

## Phase 2
- ☑ Add reusable channel-composition wiring that always includes `EmailChannel` and `SMSChannel`.
- ☑ Replace duplicated notifier construction in weekly-summary and special-case entrypoints with the shared channel builder.
- ☑ Ensure Twilio config is required in non-testing runtime and not required in testing runtime.
- ☑ Add wiring tests for mandatory SMS channel composition.

## Phase 3
- ☑ Preserve `NOTIFICATION_LOG` semantics while including SMS channel outcomes in notifier results/error aggregation.
- ☑ Make notifier dispatch preference-aware so each user is attempted only on channels present in their `notifPrefs`.
- ☑ Add notifier-level tests proving SMS failures do not halt job/intent execution and partial success still logs `sent`.

## Phase 4
- ☐ Update architecture and notification documentation to reflect SMS channel/provider additions and preference-aware multi-channel dispatch.
- ☐ Update runtime/deployment docs with SMS env contract and enablement behavior (no Docker topology changes).

## Phase 1: SMS Provider + Channel Primitives
Affected files and changes
- `backend/services/notifications/providers/sms_provider.py` (new): define `SMSProvider` contract with `send(*, to: str, body: str) -> SMSProviderResult` plus `SMSProviderError` for transport/config failures.
- `backend/services/notifications/providers/twilio_sms_provider.py` (new): implement Twilio REST integration (`requests`) using account SID/auth token/phone number, returning `SMSProviderResult`.
- `backend/services/notifications/channels/sms_channel.py` (new): implement `SMSChannel` with payload-to-text rendering, phone presence check, provider send call, and normalized channel result.
- `backend/services/notifications/types.py`: widen `ChannelStatus` to include `"skipped"`; keep `NotifyResult` shape intact.
- `backend/services/notifications/interfaces.py`: keep shared `NotificationChannel` protocol, now supporting channel-level skipped results.
- `backend/services/notifications/channels/__init__.py`: export `SMSChannel`.
- `backend/services/notifications/providers/__init__.py`: export SMS provider types + Twilio implementation.

Implementation details
- `TwilioSMSProvider` constructor args: `account_sid`, `auth_token`, `from_phone`, optional `timeout_seconds`.
- `SMSProviderResult` typed shape includes at minimum `messageId: str` and can be extended later without breaking caller contracts.
- Twilio send endpoint: `POST https://api.twilio.com/2010-04-01/Accounts/{AccountSid}/Messages.json` with Basic Auth.
- Request form fields: `From`, `To`, `Body`; response must include `sid` on success.
- Non-2xx or malformed success response raises `SMSProviderError` with concise diagnostic text.
- `SMSChannel.send(payload)` behavior:
  - Build SMS body from intent payload (`weekly-summary` and `mail-arrived` variants) using small deterministic formatter helpers.
  - Resolve `user.phone`; if missing/blank, return `{channel: "sms", status: "skipped", error: "missing phone"}`.
  - On provider success: `{channel: "sms", status: "sent", messageId: <provider_result.messageId>}`.
  - On provider error/exception: `{channel: "sms", status: "failed", error: <message>}`.
- Keep channel free of preference checks; only explicit invocation controls use.

Unit tests (phase-local)
- `backend/tests/test_twilio_sms_provider.py` (new):
  - `test_send_posts_twilio_message_and_returns_sid`
  - `test_send_raises_sms_provider_error_on_http_error`
  - `test_send_raises_sms_provider_error_when_sid_missing`
- `backend/tests/test_sms_channel.py` (new):
  - `test_send_weekly_summary_returns_skipped_when_phone_missing`
  - `test_send_special_case_formats_body_and_calls_provider`
  - `test_send_returns_failed_when_provider_raises`
  - `test_send_returns_sent_with_message_id_on_success`

## Phase 2: Channel Wiring + Config Gate
Affected files and changes
- `backend/services/notifications/channels/factory.py` (new): add `build_notification_channels(*, testing: bool) -> list[NotificationChannel]` that always includes `EmailChannel` and `SMSChannel`.
- `backend/services/notifications/providers/factory.py`: add `build_sms_provider(*, testing: bool) -> SMSProvider` and env-loading helper for Twilio keys.
- `backend/services/notifications/weekly_summary_cron_job.py`: update eligible-user selection to be decoupled from a hardcoded email preference and aligned to enabled channels.
- `backend/repositories/users_repository.py`: add repository helper for weekly-summary candidate IDs based on channel preference set (instead of single fixed preference).
- `backend/controllers/notifications_controller.py`: use shared channel factory for weekly-summary notifier creation.
- `backend/controllers/internal_jobs_controller.py`: use shared channel factory for internal weekly job notifier creation.
- `backend/controllers/mail_requests_controller.py`: use shared channel factory for special-case notifier creation.
- `backend/services/mail_request_service.py`: route default special-case notifier through shared channel factory to keep behavior consistent across service/controller entrypoints.
- `backend/scripts/run_weekly_summary_cron.py`: use shared channel factory in default notifier builder.

Implementation details
- `build_notification_channels` always includes SMS and email channels.
- Missing `TWILIO_*` env raises provider/config error in non-testing runtime.
- Testing runtime uses console SMS provider and does not require `TWILIO_*` env.
- Weekly-summary candidate lookup should accept the currently enabled channel preference set (for example `["email"]` or `["email", "text"]`) and select users with any intersection.
- Testing mode behavior:
  - keep email provider as console provider (existing behavior).
  - for SMS, either use a lightweight console/fake provider path in factory or explicit test doubles where channel/provider tests patch network calls.
- Centralize notifier channel composition so weekly/special-case flows stay synchronized and avoid wiring drift.

Unit tests (phase-local)
- `backend/tests/test_provider_factory.py`:
  - add `test_build_sms_provider_returns_twilio_provider_when_env_present`
  - add `test_build_sms_provider_raises_when_twilio_env_missing`
  - add `test_build_sms_provider_returns_console_provider_in_testing_mode`
- `backend/tests/test_weekly_summary_cron_command.py`:
  - assert default notifier channels come from shared builder.
- `backend/tests/test_weekly_summary_cron_job.py`:
  - assert candidate-user query uses enabled channel preference set (not hardcoded `"email"` only).
- `backend/tests/test_weekly_summary_scheduler_endpoint.py` and `backend/tests/test_admin_session_auth.py`:
  - patch shared channel builder and assert controllers build notifiers with composed channels instead of hardcoded email-only channel list.

## Phase 3: Logging Semantics + Resilience + Docs
Affected files and changes
- `backend/services/notifications/weekly_summary_notifier.py`: make dispatch preference-aware by filtering configured channels against user `notifPrefs`, then normalize channel results with support for `status="skipped"` and top-level status derivation (`sent` if any sent, `failed` if none sent and any failed, `skipped` if all skipped).
- `backend/services/notifications/special_case_notifier.py`: apply the same preference-aware channel filtering and status normalization.
- `backend/repositories/users_repository.py`: include `phone` and `notifPrefs` in notification profile lookups used by notifiers.
- `backend/tests/test_weekly_summary_notifier.py`: add multi-channel cases including SMS skipped/failure + email success.
- `backend/tests/test_special_case_notifier.py`: add multi-channel cases including SMS skipped/failure + email success.
- `docker-compose.yml`: add Twilio env passthrough under `backend.environment`.

Implementation details
- Continue single attempt log per notifier invocation in `NOTIFICATION_LOG`; do not add per-channel log rows.
- Ensure aggregated error message includes SMS error text when all channels fail.
- Preserve existing weekly summary aggregation/mail logic; only channel list and channel-result normalization change.
- Notifier top-level status after channel dispatch:
  - `sent` if any channel `sent`
  - `failed` if no channels sent and at least one channel `failed`
  - `skipped` if all channels `skipped`
- No Docker service additions, removals, or network/topology changes.

Unit tests (phase-local)
- `backend/tests/test_weekly_summary_notifier.py`:
  - `test_notify_weekly_summary_uses_only_user_preferred_channels`
  - `test_notify_weekly_summary_returns_sent_when_email_sent_and_sms_skipped`
  - `test_notify_weekly_summary_logs_failed_when_email_and_sms_fail`
  - `test_notify_weekly_summary_returns_skipped_when_all_channels_skip`
  - `test_notify_weekly_summary_does_not_raise_when_sms_channel_raises`
- `backend/tests/test_special_case_notifier.py`:
  - `test_notify_special_case_uses_only_user_preferred_channels`
  - `test_notify_special_case_returns_sent_when_email_sent_and_sms_skipped`
  - `test_notify_special_case_logs_failed_when_email_and_sms_fail`
  - `test_notify_special_case_returns_skipped_when_all_channels_skip`
  - `test_notify_special_case_does_not_raise_when_sms_channel_raises`

## Phase 4: Documentation + Architecture Artifacts
Affected files and changes
- `README.md`: document `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`, and the preference-aware multi-channel dispatch behavior.
- `deployment.md`: add Twilio runtime env requirements for backend service.
- `docs/architecture/notification-system.md`: update intent/channel/provider sections to include SMS channel and Twilio provider wiring.
- `docs/architecture/overview.md`: update communication boundary examples to include backend-to-SMS-provider integration.
- `docs/architecture/diagrams/user-notification-flow.mmd`: include per-user channel filtering by `notifPrefs` and parallel/independent channel attempts.
- `docs/architecture/diagrams/admin-mail-logging-flow.mmd`: include SMS attempt outcomes in special-case notifier flow while preserving single log-entry semantics.
- `docs/architecture/diagrams/internal-layer-interaction-sequence.mmd`: reflect SMS channel/provider path while preserving `app.py -> controllers -> services -> channels -> providers`.
- `docs/architecture/diagrams/container-diagram.mmd`: include external SMS provider boundary from backend container (no container topology changes).

Implementation details
- Keep docs consistent with code behavior:
  - intent-level eligibility decoupled from individual channel preference values
  - channel attempt filtering by `notifPrefs` (`email`, `text`)
  - status derivation (`sent` / `failed` / `skipped`) and failure isolation guarantees
  - `NOTIFICATION_LOG` remains one row per notifier invocation, not per channel
- Keep deployment/topology statements explicit: no new internal containers/services; SMS provider is an external dependency.

Unit tests (phase-local)
- No code unit tests in this phase; this phase only updates documentation artifacts to match implemented behavior.
