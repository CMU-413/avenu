# Open Questions
- None.

# Locked Decisions
- Keep `"text"` in persisted `notifPrefs`; expose `smsNotifications` only at API/UI boundaries.
- Centralize `"text"` <-> `smsNotifications` mapping in a single normalization helper so storage enum values do not leak across services/controllers.
- `PATCH /api/member/preferences` uses partial semantics: `emailNotifications` and `smsNotifications` are independently optional; omitted fields are unchanged.
- Backend must enforce phone-required SMS preference even when frontend is bypassed.
- Phone-required validation failures return `400` with exact message: `"SMS notifications require a valid phone number"`.
- Removing phone must auto-remove SMS preference server-side.
- Phone missing includes `None`, empty string, and whitespace-only values.
- Session payload exposes `emailNotifications`, `smsNotifications`, and `hasPhone`; raw phone is not exposed for this ticket.
- Weekly summary dispatch remains preference-aware and failure-isolated across channels.

# Task Checklist
## Phase 1
- ☑ Add a shared effective-state normalization helper used by both admin and member preference update paths.
- ☑ Enforce SMS preference invariants in backend update flows (`notifPrefs` + phone coupling) using the shared helper.
- ☑ Extend member/session preference API contracts to carry `smsNotifications` and phone presence for UI gating.
- ☑ Add backend unit tests for reject/auto-remove behavior and response contracts.

## Phase 2
- ☑ Wire member UI state and API client to support both email and SMS preferences.
- ☑ Add SMS toggle with disabled state and inline guidance when phone is missing.
- ☑ Ensure outgoing preference payload auto-clears SMS when phone is absent.
- ☑ Add focused frontend unit tests for payload normalization logic.

## Phase 3
- ☑ Ensure notifier dispatch explicitly attempts SMS only when SMS preference is enabled.
- ☑ Add channel-level structured logging so SMS attempts emit `channel="sms"` entries.
- ☑ Add/extend notifier unit tests for SMS preference filtering and sms-channel log emission.

## Phase 1: Backend Preference Validation + API Contract
Affected files and changes
- `backend/services/user_preferences.py` (new): add a single helper that merges current user state + incoming preference/phone patch, enforces phone-required SMS, auto-removes SMS when phone missing, and returns both normalized storage values (`notifPrefs`) and API booleans (`emailNotifications`, `smsNotifications`, `hasPhone`).
- `backend/models/builders.py`: keep enum parsing for create/patch models; avoid duplicating preference mapping rules outside the shared helper.
- `backend/services/user_service.py`: admin user patch path loads current user and delegates to shared normalization helper before persistence; applies normalized `notifPrefs` and any phone update.
- `backend/services/member_service.py`: replace email-only updater with partial preference updater that delegates to shared normalization helper and persists normalized storage values.
- `backend/controllers/member_controller.py`: accept/validate `smsNotifications` alongside `emailNotifications` (partial patch semantics), route to new member preference service method.
- `backend/controllers/session_controller.py`: include `smsNotifications` and `hasPhone` in `/api/session/me` response.
- `backend/tests/test_admin_session_auth.py`: update existing member preference endpoint tests and add cases for SMS enabled/disabled validation and 400 error contract.
- `backend/tests/test_user_service.py` (new or extended): add admin patch-path coverage for helper-backed normalization.
- `backend/tests/test_member_service.py` (new or extended): add member preference update coverage for partial patch behavior.
- `backend/tests/test_models.py`: add focused tests for preference normalization helper behavior where relevant.

Implementation details
- Effective-state validation runs after merging stored values with patch values, so `notifPrefs`-only updates cannot bypass phone checks.
- Phone emptiness treats `None`, empty string, and whitespace-only as missing.
- Auto-remove behavior applies both to admin user patch path and member self-service preference path.
- Member preference response shape should include both booleans (`emailNotifications`, `smsNotifications`) and remain storage-agnostic.
- Session hydration response exposes `emailNotifications`, `smsNotifications`, and `hasPhone` so UI can disable SMS without fetching raw phone.
- Helper return shape should include both:
  - storage-facing fields for persistence (`notifPrefs`, optional normalized `phone`)
  - API-facing fields for response/session (`emailNotifications`, `smsNotifications`, `hasPhone`)

Unit tests (phase-local)
- `backend/tests/test_admin_session_auth.py`
  - `test_member_preferences_accepts_sms_toggle_when_phone_present`
  - `test_member_preferences_rejects_sms_toggle_without_phone_returns_400`
  - `test_member_preferences_returns_sms_state_in_response`
  - `test_member_preferences_accepts_partial_updates`
- `backend/tests/test_user_service.py` (or equivalent)
  - `test_update_user_rejects_text_pref_when_effective_phone_missing`
  - `test_update_user_auto_removes_text_pref_when_phone_cleared`
- `backend/tests/test_member_service.py` (or equivalent)
  - `test_update_member_preferences_partial_patch_leaves_omitted_fields_unchanged`
  - `test_update_member_preferences_rejects_sms_without_phone`
  - `test_update_member_preferences_returns_email_sms_and_has_phone`
- `backend/tests/test_models.py` or `backend/tests/test_user_preferences.py` (preferred)
  - `test_normalize_effective_preferences_merges_current_and_patch`
  - `test_normalize_effective_preferences_treats_whitespace_phone_as_missing`
  - `test_normalize_effective_preferences_strips_text_when_phone_missing`

## Phase 2: Frontend SMS Toggle + Payload Wiring
Affected files and changes
- `frontend/src/lib/api/contracts/types.ts`: extend `ApiSessionMe` and `ApiMemberPreferences` with `smsNotifications` and `hasPhone`.
- `frontend/src/lib/store.ts`: extend `SessionUser` to store SMS preference and phone presence; add updater for both preference fields.
- `frontend/src/lib/api/routes/member.ts`: change `updateMemberPreferences` to accept an object payload (`emailNotifications?`, `smsNotifications?`) and return updated dual-preference state.
- `frontend/src/App.tsx`: update session-hydration mapping to include new fields.
- `frontend/src/pages/Login.tsx`: update post-login mapping to include SMS/phone fields.
- `frontend/src/pages/member/NotificationSettings.tsx`: add SMS toggle row, disable when phone missing, show inline message, and auto-clear SMS in payload/state when phone is absent.
- `frontend/src/lib/member-preferences.ts` (new): add pure helper(s) to normalize outgoing preference payload and enforce no-SMS-without-phone invariant client-side.
- `frontend/src/test/member-preferences.test.ts` (new): unit tests for normalization helper (no component/integration tests).

Implementation details
- UI label remains “SMS Notifications”; persistence stays backend-managed via booleans from member API.
- Disabled SMS toggle copy should explain requirement inline (for example: “Add a phone number to enable SMS notifications.”).
- Auto-remove behavior in UI should be deterministic on render/update: if `hasPhone` becomes false and SMS is true in local state, send a normalized patch with `smsNotifications=false`.
- Keep optimistic update rollback behavior consistent with existing email toggle flow.

Unit tests (phase-local)
- `frontend/src/test/member-preferences.test.ts`
  - `buildPreferencePatch_clears_sms_when_phone_missing`
  - `buildPreferencePatch_preserves_sms_when_phone_present`
  - `buildPreferencePatch_supports_partial_toggle_updates`
  - `deriveSettingsState_disables_sms_without_phone`

## Phase 3: Dispatch Guard + SMS Channel Logging
Affected files and changes
- `backend/services/notifications/weekly_summary_notifier.py`: keep preference-filtered channel dispatch; ensure SMS channel is attempted only when SMS preference is enabled and emit structured per-channel logs for `sent`, `failed`, and `skipped` with `channel=<channel>`.
- `backend/services/notifications/special_case_notifier.py`: apply the same structured per-channel logging pattern for parity and full SMS observability.
- `backend/services/notifications/types.py`: if needed, tighten channel-result/log typing to include `"skipped"` and optional channel error metadata used in logs.
- `backend/tests/test_weekly_summary_notifier.py`: extend with assertions that SMS channel is skipped when preference absent and per-channel logger entries include `channel=sms` when attempted.
- `backend/tests/test_special_case_notifier.py`: add equivalent assertions for special-case notifier channel logging.

Implementation details
- Preserve failure isolation: any channel exception stays localized to that channel result and does not abort notifier flow.
- Structured logger fields for each channel attempt should include at minimum `channel`, `status`, and `userId`; SMS attempts must produce `channel="sms"` log entries across sent/failed/skipped outcomes.
- Do not change top-level notify status derivation (`sent` if any sent, `failed` if none sent and any failed, `skipped` when all skipped/pre-dispatch).

Unit tests (phase-local)
- `backend/tests/test_weekly_summary_notifier.py`
  - `test_notify_weekly_summary_attempts_sms_only_when_sms_pref_enabled`
  - `test_notify_weekly_summary_logs_channel_sms_for_sent_failed_and_skipped`
- `backend/tests/test_special_case_notifier.py`
  - `test_notify_special_case_attempts_sms_only_when_sms_pref_enabled`
  - `test_notify_special_case_logs_channel_sms_for_sent_failed_and_skipped`
