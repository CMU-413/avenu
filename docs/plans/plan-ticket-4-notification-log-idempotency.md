# Open Questions
None.

# Locked Decisions
- Duplicate idempotency (`already_sent`) creates a new `NOTIFICATION_LOG` row with `status="skipped"` and `reason="already_sent"`; prior `sent` rows remain unchanged.
- This ticket does not include cron/admin endpoint wiring; acceptance for "cron run twice" and "admin trigger" is proven with notifier-level unit tests.
- Add `reason` as a structured outcome field (`already_sent|opted_out|empty_summary|user_not_found|all_channels_failed`) and reserve `errorMessage` for concrete error text.
- Normalize `weekStart` deterministically before log query/insert so idempotency keying uses one canonical boundary representation.
- Keep lookup indexes on `(userId, type, weekStart, status)` without unique constraints to allow multiple audited attempts.

# Task Checklist
## Phase 1
- ☑ Add `NOTIFICATION_LOG` collection wiring and indexes in config.
- ☑ Add notification-log status/reason typing for notifier outcomes, including duplicate-skip reason and explicit log `reason` field.
- ☑ Add a small notification-log repository helper for typed insert/find operations.

## Phase 2
- ☑ Integrate notification-log persistence into `WeeklySummaryNotifier` so every invocation writes a log row.
- ☑ Add pre-send idempotency check for prior `sent` weekly-summary records by `(userId, type, weekStart)`.
- ☑ Return `skipped` for duplicates without dispatching channels, while preserving existing behavior for opted-out/empty/user-not-found/all-channels-failed.
- ☑ Normalize `weekStart` before lookup/insert so idempotency checks and log writes use deterministic date boundaries.

## Phase 3
- ☑ Add/extend unit tests to prove logging for all outcomes and duplicate prevention for cron/admin triggers.
- ☑ Keep tests in-memory with lightweight fakes (no integration tests, no complex mocks).

## Phase 1: Notification Log Persistence Primitives
Affected files and changes
- `backend/config.py`: add `notification_log_collection = db["notification_log"]`; add non-unique indexes for efficient idempotency lookup (`userId`, `type`, `weekStart`, `status`) and auditing (`userId`, `weekStart`).
- `backend/services/notifications/types.py`: extend unions to include duplicate-skip reason (e.g. `already_sent`) and add typed literals for notification-log status/type (`weekly-summary`, `sent|skipped|failed`).
- `backend/services/notifications/log_repository.py` (new): add focused functions for `find_sent_weekly_summary(...)` and `insert_notification_log(...)` with explicit typed payload shapes.
- `backend/services/notifications/__init__.py`: export the new repository helper(s) if this package is used as a public import surface.

### Persistence/data decisions
- `NOTIFICATION_LOG` schema for each row:
  - `userId: ObjectId`
  - `type: "weekly-summary"`
  - `weekStart: date`
  - `status: "sent" | "skipped" | "failed"`
  - `reason: "already_sent" | "opted_out" | "empty_summary" | "user_not_found" | "all_channels_failed" | None`
  - `triggeredBy: "cron" | "admin"`
  - `errorMessage: str | None` (only populated with concrete runtime error text)
  - `sentAt: datetime | None` (`None` unless status is `sent`)
  - `createdAt: datetime` (append-only audit timestamp)
- Keep repository helper narrowly scoped to value-oriented data operations (no channel dispatch or summary computation).

### Unit tests (phase-local)
- No direct test file in this phase; behavior is validated through notifier tests in Phase 3.

## Phase 2: WeeklySummaryNotifier Idempotency + Attempt Logging
Affected files and changes
- `backend/services/notifications/weekly_summary_notifier.py`: inject `notificationLogCollection` (defaulting from config), perform idempotency pre-check before summary/channel dispatch, and append one log record per invocation outcome.
- `backend/services/notifications/interfaces.py`: keep notifier interface stable; only update types/imports if needed by expanded `NotifyReason`.
- `backend/config.py`: wire import for `notification_log_collection` into notifier defaults where applicable.

### Notifier flow updates
- At method start, derive immutable keys:
  - `type = "weekly-summary"`
  - normalized `weekStart` from input
  - `userId`, `triggeredBy`
- Idempotency gate (before send):
  - Query log repository for existing row with same `userId`, `type`, `weekStart`, and `status="sent"`.
  - If found, return `{"status":"skipped","reason":"already_sent","channelResults":[]}`.
- Preserve existing guards for `user_not_found`, `opted_out`, `empty_summary`, and channel failures.
- Ensure one `insert_notification_log(...)` call for every return path:
  - `sent`: `status="sent"`, `reason=None`, `errorMessage=None`, `sentAt=now`.
  - `skipped` cases (`already_sent`, `opted_out`, `empty_summary`): `status="skipped"`, `reason=<outcome reason>`, `errorMessage=None`, `sentAt=None`.
  - `failed` cases (`user_not_found`, `all_channels_failed`): `status="failed"`, `reason=<outcome reason>`, `errorMessage=<real error text when available>`, `sentAt=None`.
- For duplicate skips, insert an additional attempt row (`status="skipped"`, `reason="already_sent"`) instead of mutating prior `sent` entries.
- Keep channel/provider behavior unchanged so `ConsoleEmailProvider` continues to work without additional branching.

### Unit tests (phase-local)
- Covered in Phase 3.

## Phase 3: Unit Tests for Notification Log + Idempotency
Affected files and changes
- `backend/tests/test_weekly_summary_notifier.py`: extend current notifier tests with log collection fakes and assertions on inserted log rows.
- `backend/tests/test_idempotency.py` (optional extension) or `backend/tests/test_notification_log_idempotency.py` (new): add focused tests for notification-log duplicate prevention semantics to keep notifier tests readable.

### Unit tests
- `test_notify_weekly_summary_logs_sent_attempt`
  - Arrange successful channel send.
  - Assert top-level `sent`.
  - Assert one log row with `status="sent"`, `type="weekly-summary"`, matching `userId/weekStart/triggeredBy`, and non-null `sentAt`.
- `test_notify_weekly_summary_logs_skipped_for_opted_out`
  - Assert `skipped/opted_out` and corresponding log row with `status="skipped"`, `reason="opted_out"`, and `errorMessage is None`.
- `test_notify_weekly_summary_logs_failed_when_all_channels_fail`
  - Assert `failed/all_channels_failed` and log row with `status="failed"`, `reason="all_channels_failed"`, plus non-empty `errorMessage` when a runtime error exists.
- `test_notify_weekly_summary_duplicate_week_is_skipped_for_cron`
  - First call returns `sent`, second call (same `userId/weekStart`, triggeredBy=`cron`) returns `skipped/already_sent`.
  - Assert channel send count is `1` across both calls.
  - Assert two log rows exist: first `sent`, second `skipped` with `reason="already_sent"`.
- `test_notify_weekly_summary_duplicate_week_is_skipped_for_admin`
  - Invoke notifier twice with `triggeredBy="admin"` and assert trigger source does not bypass idempotency (send count remains `1`, second row is `skipped/already_sent`).
- `test_notify_weekly_summary_duplicate_check_uses_status_sent_only`
  - Seed prior `failed` or `skipped` row for same key.
  - Assert notifier still attempts send and can transition to `sent`.

### Test constraints
- Keep tests deterministic with in-memory fake collections and fixed dates.
- No manual/QA/integration tests; no network/provider SDK mocking beyond simple fakes already used in notifier tests.
