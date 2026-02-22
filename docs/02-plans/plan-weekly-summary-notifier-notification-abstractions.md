# Open Questions
None.

# Locked Decisions
- Opt-in source: derive notification eligibility from `"email" in user.notifPrefs`.
- Top-level status semantics:
  - `sent`: at least one channel succeeds.
  - `failed`: zero channels succeed.
  - `skipped`: no channel attempts are made.
- Partial channel success is reported as top-level `sent`.
- `NotifyResult` always includes `channelResults` (empty list for skipped cases).
- `NotifyResult` includes explicit `reason` for `skipped` and `failed` outcomes.
- Notification payload models user identity as a structured `user` object, not flattened fields.
- Missing user handling: return `NotifyResult(status="failed", reason="user_not_found", channelResults=[])` without raising.

# Task Checklist
## Phase 1
- ☑ Add notification intent abstractions (`Notifier`, `NotificationChannel`, `NotifyResult`, `ChannelResult`) as typed contracts.
- ☑ Add a weekly-summary payload contract shared between notifier and channels.
- ☑ Keep abstractions provider-agnostic and free of rendering/cron concerns.

## Phase 2
- ☑ Implement `WeeklySummaryNotifier` with user loading, opt-in guard, summary retrieval, zero-mail skip, and injected channel dispatch.
- ☑ Ensure channel exceptions are captured into per-channel failure results without raising.
- ☑ Return a clean structured `NotifyResult` including skip reason/status and per-channel outcomes.

## Phase 3
- ☑ Add focused unit tests covering opted-out, empty summary, successful send, and channel failure behaviors.
- ☑ Verify tests assert no throws on channel failure and stable result shape.

## Phase 1: Notification Intent Abstractions
Affected files and changes
- `backend/services/notifications/types.py` (new): add `TypedDict` contracts for `WeeklySummaryNotificationPayload`, `ChannelResult`, and `NotifyResult`.
- `backend/services/notifications/interfaces.py` (new): add `Protocol` interfaces for `NotificationChannel` and `Notifier`.
- `backend/services/notifications/__init__.py` (new): re-export core notification abstractions for concise imports.

### Contracts
- `NotificationChannel.send(payload) -> ChannelResult` where payload contains:
  - structured target user identity object (`user: { id, email, fullname }`)
  - computed weekly summary (`weekStart`, `weekEnd`, totals, mailbox breakdown)
  - trigger metadata (`triggeredBy`)
- `Notifier.notifyWeeklySummary(...) -> NotifyResult` with explicit status union (`sent|skipped|failed`), always-present `channelResults`, and `reason` for non-sent statuses.
- Keep these modules pure typing + domain contracts (no DB access, provider SDK, rendering, or scheduling code).

### Unit tests (phase-local)
- No direct tests in this phase; type-level contracts are exercised through notifier tests in Phase 3.

## Phase 2: WeeklySummaryNotifier Implementation
Affected files and changes
- `backend/services/notifications/weekly_summary_notifier.py` (new): implement `WeeklySummaryNotifier` with dependency-injected user collection, `MailSummaryService`, and `NotificationChannel` list.

### Notifier flow
- Input: `userId`, `weekStart`, `weekEnd`, `triggeredBy`.
- Load user once; if missing, return `NotifyResult(status="failed", reason="user_not_found", channelResults=[])` (no throw).
- Resolve email opt-in from `"email" in user.notifPrefs`.
- If opted out, return `NotifyResult(status="skipped", reason="opted_out", channelResults=[])` and no channel sends.
- Call `MailSummaryService.getWeeklySummary(...)`.
- If `totalLetters + totalPackages == 0`, return `NotifyResult(status="skipped", reason="empty_summary", channelResults=[])`.
- Build one immutable notification payload value and pass it to each injected channel.
- Iterate channels independently:
  - If `send` succeeds, append returned `ChannelResult`.
  - If `send` raises, catch exception and append `{channel: <name>, status: "failed", error: str(exc)}`.
- Derive top-level status from collected channel results:
  - `sent` if at least one channel result has `status == "sent"`.
  - `failed` if no channel result succeeded.
  - `skipped` only for pre-dispatch exits above.
- For `failed` outcomes after attempted dispatch, set `reason="all_channels_failed"`.
- Never import provider SDKs, render HTML, or schedule execution here.

### Unit tests (phase-local)
- Implemented in Phase 3 against the concrete notifier behavior above.

## Phase 3: Unit Tests for Notifier Behavior
Affected files and changes
- `backend/tests/test_weekly_summary_notifier.py` (new): add notifier-focused unit tests with lightweight fakes for user store, summary service, and channels.

### Unit tests
- `test_notify_weekly_summary_skips_when_user_opted_out`
  - Arrange user with email notifications disabled.
  - Assert result is `skipped` with `reason="opted_out"` and `channelResults=[]`.
  - Assert summary service and channels are not called.
- `test_notify_weekly_summary_fails_when_user_not_found`
  - Arrange missing user lookup.
  - Assert result is `failed` with `reason="user_not_found"` and `channelResults=[]`.
  - Assert summary service and channels are not called.
- `test_notify_weekly_summary_skips_when_summary_is_empty`
  - Arrange opted-in user and summary with zero letters/packages.
  - Assert result is `skipped` with `reason="empty_summary"` and `channelResults=[]`.
  - Assert channels are not called.
- `test_notify_weekly_summary_sends_to_channels_when_summary_has_mail`
  - Arrange opted-in user and non-empty summary.
  - Arrange one successful fake channel and optionally one failing channel.
  - Assert top-level `sent` (partial success rule) and expected `channelResults` content/order.
- `test_notify_weekly_summary_collects_channel_failure_without_throwing`
  - Arrange all channels failing (raised exception and/or returned failed status).
  - Assert method returns normally.
  - Assert failed channel results include error text where applicable.
  - Assert top-level result is `failed` with `reason="all_channels_failed"`.

### Test design constraints
- Keep tests unit-only with in-memory fakes; avoid integration tests and complex mocking.
- Reuse deterministic week dates and ObjectIds to match existing backend test style.
