# Open Questions
None.

# Locked Decisions
- Weekly job execution will reuse `WeeklySummaryNotifier.notifyWeeklySummary(...)` as the only dispatch entrypoint.
- Cron/manual execution will compute a deterministic previous full week window from one clock source (`now` injected for tests, UTC in production), anchored to UTC Monday-Sunday.
- Opted-in audience is users where `notifPrefs` contains `"email"`.
- Job execution is best-effort per user: per-user failures are logged and do not stop remaining users.
- Job emits explicit start/completion logs with week window and explicit counters (`processed`, `sent`, `skipped`, `failed`, `errors`).
- Duplicate sends are prevented by notifier-level idempotency (`already_sent` / existing `sent` log), not by extra job-level dedupe state.
- Scope is command-only execution for external cron/platform schedulers; no in-process scheduler wiring in backend.

# Task Checklist
## Phase 1
- ☑ Add a weekly job module that computes previous-week boundaries deterministically and iterates opted-in users.
- ☑ Add structured job lifecycle logging (start, per-user exception, completion counters).
- ☑ Keep the job logic value-oriented and notifier-driven (no channel/provider branching inside the loop).

## Phase 2
- ☑ Add a manual-run command entrypoint that instantiates notifier dependencies and runs the weekly job once.
- ☑ Ensure manual execution uses the same notifier path/channels so `ConsoleEmailProvider` output remains the observable send output.

## Phase 3
- ☑ Add unit tests for week-range computation, opted-in user filtering, continue-on-failure semantics, and notifier-call arguments.
- ☑ Add unit tests for manual-run wiring that prove notifier entrypoint reuse and expected console-provider output path.

## Phase 1: Weekly Job Orchestration
Affected files and changes
- `backend/services/notifications/weekly_summary_cron_job.py` (new): implement deterministic week-window helpers and the core job runner that loops opted-in users and invokes notifier.
- `backend/services/notifications/__init__.py`: export cron-job functions/types for straightforward reuse by CLI/scheduler wiring.
- `backend/services/notifications/types.py` (optional small extension): add a typed `WeeklyCronJobResult` shape for counts (`processed`, `sent`, `skipped`, `failed`, `errors`).

### Core behavior
- Add `compute_previous_week_range(now: datetime) -> tuple[date, date]`:
  - Normalize `now` to UTC before deriving date boundaries.
  - Derive previous full Monday-Sunday range deterministically.
  - Return immutable `(week_start, week_end)` values.
- Add `run_weekly_summary_cron_job(...)` function with injected dependencies (`notifier`, `users collection`, `now`, `logger`).
- Query opted-in users with projection-first query (`{"notifPrefs": {"$in": ["email"]}}` with `{"_id": 1}`).
- For each user:
  - Call `notifier.notifyWeeklySummary(userId=..., weekStart=..., weekEnd=..., triggeredBy="cron")`.
  - Increment counters by returned status.
  - Catch unexpected exceptions, log user context, increment `errors`, continue loop.
- Emit start log with `weekStart`, `weekEnd`, and candidate user count.
- Emit completion log with explicit counters (`processed`, `sent`, `skipped`, `failed`, `errors`) and elapsed duration.

### Unit tests (phase-local)
- Implemented in Phase 3.

## Phase 2: Manual Run Entrypoint
Affected files and changes
- `backend/scripts/run_weekly_summary_cron.py` (new): add a one-shot command entrypoint that constructs notifier dependencies and runs the job.
- `backend/services/notifications/providers/console_provider.py` (no behavior change): reused as-is by manual command for observable console output.
- `backend/app.py` or a small helper module (if needed): reuse Flask app context for template rendering through `EmailChannel`.

### Entrypoint behavior
- Build one notifier instance using existing components:
  - `EmailChannel(ConsoleEmailProvider())` for local/manual runs.
  - `WeeklySummaryNotifier(channels=[...])`.
- Enter Flask app context, execute `run_weekly_summary_cron_job(...)`, print/return a compact run summary.
- Manual command must delegate week-boundary computation to `run_weekly_summary_cron_job(...)` and must not recompute week bounds separately.
- Keep script idempotent for repeated execution; duplicate sends are skipped by notifier log checks.
- Keep this entrypoint thin: orchestration logic stays in `weekly_summary_cron_job.py`.

### Unit tests (phase-local)
- Implemented in Phase 3.

## Phase 3: Unit Tests for Cron Job + Manual Wiring
Affected files and changes
- `backend/tests/test_weekly_summary_cron_job.py` (new): unit tests for window calculation, user selection, loop behavior, and status aggregation.
- `backend/tests/test_weekly_summary_cron_command.py` (new) or extension in existing notifier/email tests: unit tests for manual-run wiring and console output path.

### Unit tests
- `test_compute_previous_week_range_uses_deterministic_monday_to_sunday_window`
  - Fixed `now` (UTC) and assert exact `weekStart/weekEnd` dates.
- `test_run_weekly_summary_cron_job_fetches_only_opted_in_users`
  - Fake users collection with mixed `notifPrefs`; assert notifier called only for `"email"` users.
- `test_run_weekly_summary_cron_job_passes_cron_trigger_and_week_bounds`
  - Assert each notifier call uses `triggeredBy="cron"` and shared computed week range.
- `test_run_weekly_summary_cron_job_continues_on_notifier_exception`
  - One user raises exception; remaining users still processed; completion counters/logs reflect `errors`.
- `test_run_weekly_summary_cron_job_logs_start_and_completion`
  - Capture logger output and assert both lifecycle messages include week window and totals.
- `test_manual_command_uses_same_notifier_entrypoint`
  - Replace notifier with a fake capturing calls; assert command invokes `notifyWeeklySummary` through job runner, not direct channel/provider sends.
- `test_manual_command_console_provider_path_emits_expected_output`
  - Execute command path with `ConsoleEmailProvider` under app context; capture stdout and assert expected email markers (e.g. `"=== EMAIL SEND ==="`, recipient, subject).

### Test design constraints
- Keep all tests unit-level with lightweight fakes (users cursor, notifier, logger); no scheduler/integration tests.
- Use fixed dates and deterministic fakes to avoid time-dependent flakiness.
