# Open Questions
- None.

# Locked Decisions
- Classification is a boolean flag `isPromotional` on the `MAIL` document. Absent/false = not promotional. Omitted from the doc when false to keep storage consistent with existing optional fields (`receiverName`, `senderInfo`).
- Toggle is admin-only: set at mail-entry create and editable via patch. No member-facing preference in this iteration.
- Feature-gated behind `FEATURE_PROMO_CLASSIFICATION` env flag, default off. Surfaced via `/api/feature-flags` as `promoClassification`, consumed by the admin UI to show/hide the toggle.
- No new index, no backfill, no migration script. `ensure_indexes()` is unchanged.
- No changes to weekly summary aggregation, notifications, dashboard counts, or member views. Tag is stored and returned; downstream consumers are out of scope.
- API surface: `POST /api/mail` accepts optional `isPromotional: bool`; `PATCH /api/mail/:id` accepts partial `isPromotional`. `GET` responses include `isPromotional` only when true (mirrors `count` convention).
- OCR auto-sort is explicitly out of scope. Classification is entered by the admin at record time.

# Task Checklist
## Phase 1
- ☑ Add `FEATURE_PROMO_CLASSIFICATION` env flag and expose via `get_feature_flags()`.
- ☑ Extend `build_mail_create` / `build_mail_patch` to parse optional `isPromotional`.
- ☑ Preserve field in `to_api_doc` / response shaping (no-op if patch carries it through untouched).
- ☑ Backend unit tests for builder parsing and service round-trip.

## Phase 2
- ☑ Extend frontend `ApiFeatureFlags` and `ApiMailRecord` types.
- ☑ Extend `createMail` / `updateMail` API clients to send `isPromotional`.
- ☑ Add toggle to admin `RecordEntry.tsx` draft + edit forms, gated on `featureFlags.promoClassification`.
- ☑ Render a `Promo` badge on existing entries when `isPromotional === true`.
- ☑ Frontend unit tests for payload normalization (toggle true → field present; false → field omitted).

---

## Phase 1: Backend field + feature flag
Affected files and changes
- `backend/config.py`
  - Add `FEATURE_PROMO_CLASSIFICATION = _env_bool("FEATURE_PROMO_CLASSIFICATION", False)`.
  - Add `"promoClassification": FEATURE_PROMO_CLASSIFICATION` to `get_feature_flags()`.
- `backend/models/builders.py`
  - `build_mail_create`: if `isPromotional` key present, coerce via `optional_bool`; include `"isPromotional": True` in the doc only when true. Unknown/absent → omit.
  - `build_mail_patch`: if `isPromotional` key present, coerce via `optional_bool` and include in patch. Patching to `false` sets the field to `False` (does not unset) — simplest behavior, still truthful for queries that check `== True`. Storage churn is negligible.
- `backend/repositories/mail_repository.py`
  - `find_mail_for_mailboxes` projection: no change. (Classification is not consumed by summary aggregation in this phase.)
- No changes to `mail_service.py`, `mail_controller.py`, or `config.ensure_indexes`.

Implementation notes
- Keep the storage shape truthful: omit `isPromotional` when false on create; preserve admin intent (explicit patch to `false`) by writing `False` on patch. This matches how the rest of the codebase treats optional booleans without over-engineering an unset path.
- No coupling to mail `type` (letter/package). Promo is orthogonal.

Unit tests (phase-local)
- `backend/tests/unit/test_models.py`
  - `test_build_mail_create_omits_is_promotional_when_absent`
  - `test_build_mail_create_sets_is_promotional_true`
  - `test_build_mail_create_omits_is_promotional_when_false`
  - `test_build_mail_patch_accepts_is_promotional_true`
  - `test_build_mail_patch_accepts_is_promotional_false_sets_field`
  - `test_build_mail_patch_rejects_non_bool_is_promotional`
- `backend/tests/unit/test_mail_service_create.py`
  - `test_create_mail_persists_is_promotional_when_true`
  - `test_create_mail_omits_is_promotional_when_absent`

---

## Phase 2: Admin UI toggle + API contract
Affected files and changes
- `frontend/src/lib/api/routes/featureFlags.ts`
  - Add `promoClassification: boolean` to `ApiFeatureFlags`.
- `frontend/src/lib/api/contracts/types.ts`
  - Add `isPromotional?: boolean` to `ApiMailRecord`.
- `frontend/src/lib/api/routes/mail.ts`
  - `createMail` payload: accept optional `isPromotional`; include in body only when `true`.
  - `updateMail` partial type: add `isPromotional?: boolean`; pass through as-is (true and false are both meaningful here).
- `frontend/src/lib/store.ts`
  - Extend `featureFlags` default/shape with `promoClassification: false`.
- `frontend/src/pages/admin/RecordEntry.tsx`
  - Extend `DraftEntry` with `isPromotional: boolean`; default `false` in `EMPTY_DRAFT`.
  - Render a checkbox "Promotional" in the draft form and the edit form, only when `featureFlags.promoClassification` is true.
  - Wire through `handleAddEntry` (pass `isPromotional: draft.isPromotional || undefined`) and `handleSaveEdit` (pass `isPromotional: editDraft.isPromotional`).
  - In entry list rendering, show a `Promo` pill next to the `letter/package` pill when `entry.isPromotional === true`.

Implementation notes
- Default `EMPTY_DRAFT.isPromotional = false`; when initializing `editDraft` from an entry, set `isPromotional: !!entry.isPromotional`.
- Payload normalization rule for `createMail`: omit when false (matches backend create semantics). For `updateMail`, include as-is — editing an entry from promo→not-promo must persist.
- No visual change when the flag is off (field hidden, payload unchanged).

Unit tests (phase-local)
- `frontend/src/lib/api/routes/__tests__/mail.test.ts` (new or extended if file exists)
  - `createMail omits isPromotional when false/undefined`
  - `createMail includes isPromotional:true when toggled on`
  - `updateMail includes isPromotional:false on explicit unset`
- No UI-level tests (per AGENTS.md: no UI/integration tests).
