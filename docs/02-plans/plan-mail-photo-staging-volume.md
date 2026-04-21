# Open Questions
- None.

# Locked Decisions
- Image bytes live on a host bind-mounted Docker volume at `IMAGE_STORE_DIR` (default `/var/lib/avenu/images`). Filename pattern: `<ObjectId>.<ext>`, derived from upload content-type.
- OCR auto-extract is gated behind a new `FEATURE_OCR_AUTO_EXTRACT` env flag (default off). When off, uploads land as `pending` queue items with empty `receiverName` / `senderInfo`, and the existing review UI lets the admin fill them in by hand. When on, the existing background OCR thread runs unchanged.
- New `OCR_QUEUE_ITEM` documents store an optional `imagePath: str` (relative to `IMAGE_STORE_DIR`). Existing `fileId` (GridFS ObjectId) field stays for backwards-compat reads.
- Image read endpoint resolves in order: `imagePath` → filesystem; fallback `fileId` → GridFS. No data migration is performed; old uploads keep working untouched.
- Retention: hard 24h. A nightly cleanup deletes any image file with mtime older than 24h AND any `OCR_QUEUE_ITEM` doc with `createdAt` older than 24h regardless of status. No exceptions for "forgotten" pending items — that's the contract.
- Cleanup is triggered by the existing `scheduler` container hitting a new internal admin endpoint `POST /api/internal/jobs/prune-staged-images` authenticated with `SCHEDULER_INTERNAL_TOKEN`. Cron expression configurable via new `IMAGE_PRUNE_CRON` (default `0 3 * * *` local time).
- Scheduler now supports two independent cron schedules: existing weekly summary (`SCHEDULER_CRON`) and new image prune (`IMAGE_PRUNE_CRON`). Both share the tick loop; loop minute-key dedupe is per-job.
- Existing OCR queue UI label/route remains; no rename in this iteration. Admin enables the workflow with `FEATURE_ADMIN_OCR=true` + `FEATURE_OCR_QUEUE_V2=true` (already exists). `FEATURE_OCR_AUTO_EXTRACT` is the only new flag the operator needs to know about.

# Task Checklist
## Phase 1 — Backend storage abstraction + flag
- ☑ Add `IMAGE_STORE_DIR` and `FEATURE_OCR_AUTO_EXTRACT` env handling in `backend/config.py`; expose `get_feature_flags()['ocrAutoExtract']` for parity with other flags.
- ☑ New `backend/services/image_store.py`: `save_bytes(data, content_type) -> str` (returns relative path), `open_path(rel_path) -> (stream, content_type)`, `delete_path(rel_path) -> bool`, `prune_older_than(seconds) -> int`. No Mongo; pure filesystem.
- ☑ Extend `OCR_QUEUE_ITEM` schema doc + `repositories/ocr_queue_repository.create_ocr_queue_items` to accept and persist `image_paths` alongside (or instead of) `file_ids`.
- ☑ Backend unit tests for `image_store` (round-trip, delete, prune-by-mtime) using `tmp_path`.

## Phase 2 — Wire upload + read + skip-OCR path
- ☑ `controllers/ocr_queue_controller.create_job`: write each upload via `image_store.save_bytes` (not `fs.put`), pass `image_paths` to `create_ocr_queue_items`. Keep `fileId` writes for any legacy code path that already relies on GridFS (none today besides this controller — drop the GridFS write).
- ☑ `controllers/ocr_queue_controller.create_job`: skip the background OCR thread when `FEATURE_OCR_AUTO_EXTRACT` is false; mark items `pending` with no `rawText`.
- ☑ `controllers/ocr_queue_controller.get_item_image`: prefer `imagePath` via `image_store.open_path`; fall back to `fs.get(fileId)` when `imagePath` absent (legacy items).
- ☑ `_serialize_item` exposes `imagePath` (string) so the frontend has a stable shape; existing `fileId` field remains.
- ☑ Backend unit tests covering: skip-OCR upload path leaves items `pending`; image read prefers filesystem; fallback to GridFS works.

## Phase 3 — Nightly prune endpoint + scheduler
- ☑ New `controllers/internal_jobs_controller` route `POST /api/internal/jobs/prune-staged-images`, internal-token guarded. Body optional `{"olderThanHours": int}` with default `IMAGE_RETENTION_HOURS=24`. Returns `{filesDeleted, itemsDeleted, errors}`.
- ☑ Service `services/image_pruner.py`: orchestrates filesystem prune + queue-item deletion in one transactional-best-effort sweep (per-doc tolerant of partial failures, returns counts).
- ☑ `scheduler/config.py` + `scheduler/main.py`: add second cron (`IMAGE_PRUNE_CRON`, default `0 3 * * *`); each tick checks both schedules independently; `last_processed_minute` becomes a per-job dict.
- ☑ `scheduler/client.py`: new `trigger_image_prune(token)` method analogous to `trigger_weekly_summary`.
- ☑ Backend unit test for prune service (creates fake old + new files, verifies only old removed; verifies queue items pruned by `createdAt`).
- ☑ Scheduler unit test for two-job tick dedupe (same minute fires once per job, different cron windows fire independently).

## Phase 4 — Compose volume + docs
- ☑ `docker-compose.yml`: add `mail-images` named volume bound to host dir; mount at `/var/lib/avenu/images`; pass `IMAGE_STORE_DIR`, `IMAGE_RETENTION_HOURS`, `FEATURE_OCR_AUTO_EXTRACT` env vars to backend; pass `IMAGE_PRUNE_CRON` to scheduler.
- ☑ `docker-compose-prod.yml`: same, with `device: ${MAIL_IMAGES_DIR:-/mnt/Main/other/AvenuMailImages/}` to match the Prometheus pattern.
- ☑ `docs/01-architecture/diagrams/data-model.mmd`: add `imagePath` field on `OCR_QUEUE_ITEM`.

---

## Phase 1: Backend storage abstraction + flag
Affected files and changes
- `backend/config.py`
  - `IMAGE_STORE_DIR = os.getenv("IMAGE_STORE_DIR", "/var/lib/avenu/images")` (created on startup if missing).
  - `IMAGE_RETENTION_HOURS = _env_positive_int("IMAGE_RETENTION_HOURS", 24)`.
  - `FEATURE_OCR_AUTO_EXTRACT = _env_bool("FEATURE_OCR_AUTO_EXTRACT", False)`.
  - Add `"ocrAutoExtract": FEATURE_OCR_AUTO_EXTRACT and FEATURE_ADMIN_OCR` to `get_feature_flags()`.
- `backend/services/image_store.py` (new)
  - Pure-stdlib module. No Flask, no Mongo. Uses `pathlib`, `secrets.token_hex`, `mimetypes`.
  - `save_bytes(data: bytes, content_type: str) -> str`: choose extension from content-type (`image/png` → `.png`, etc; default `.bin`); write to `IMAGE_STORE_DIR/<token_hex(12)>.<ext>`; return relative path string.
  - `open_path(rel_path: str) -> tuple[BinaryIO, str]`: validates the resolved path is inside `IMAGE_STORE_DIR` (no traversal); returns open binary stream and inferred content type.
  - `delete_path(rel_path: str) -> bool`: best-effort unlink; returns success.
  - `prune_older_than(seconds: int) -> int`: walks `IMAGE_STORE_DIR`, unlinks files where `mtime < now - seconds`; returns count.
- `backend/repositories/ocr_queue_repository.py`
  - `create_ocr_queue_items(job_id, count, *, image_paths: list[str] | None = None, file_ids: list[ObjectId] | None = None)`: persist `imagePath` and/or `fileId` per item.

Implementation notes
- Path validation in `open_path`: `Path(IMAGE_STORE_DIR).resolve() in resolved.parents` — refuse anything else with `APIError(404)`.
- `save_bytes` returns a *relative* path so storage dir can move without DB rewrites.
- No write fan-out to GridFS. New code path is one place: `save_bytes`.

Unit tests (phase-local)
- `backend/tests/unit/test_image_store.py`
  - `test_save_then_open_round_trips_bytes_and_content_type`
  - `test_save_uses_content_type_extension`
  - `test_open_path_rejects_traversal`
  - `test_delete_path_returns_false_when_missing`
  - `test_prune_older_than_only_deletes_stale_files`

---

## Phase 2: Wire upload + read + skip-OCR path
Affected files and changes
- `backend/controllers/ocr_queue_controller.py`
  - Replace the GridFS write loop with `image_paths = [save_bytes(data, ct) for data, ct in image_payloads]`.
  - Pass `image_paths=image_paths` to `create_ocr_queue_items`.
  - Skip background thread launch entirely when `not FEATURE_OCR_AUTO_EXTRACT`. Items are left `pending`.
  - `get_item_image`: if `item.get("imagePath")`, stream via `image_store.open_path`; else fall back to existing `fs.get(item["fileId"])`. Raise `404` if neither present.
  - `_serialize_item`: include `imagePath` field.
- `backend/config.py`
  - Surface `IMAGE_RETENTION_HOURS` (used in Phase 3 but cheaper to add here).

Implementation notes
- Keep `from config import fs` — it's only needed by the GridFS fallback branch and by any legacy admin page that surfaces ad-hoc uploads.
- `_process_ocr_job` is unchanged, just no longer started in skip-OCR mode.

Unit tests (phase-local)
- `backend/tests/unit/test_ocr_queue_controller.py`
  - `test_create_job_skips_ocr_thread_when_feature_off` (assert no thread started; items remain `pending`).
  - `test_create_job_writes_image_paths_to_items`
  - `test_get_item_image_prefers_filesystem_path`
  - `test_get_item_image_falls_back_to_gridfs_when_no_path`

---

## Phase 3: Nightly prune endpoint + scheduler
Affected files and changes
- `backend/services/image_pruner.py` (new)
  - `prune_staged_images(*, older_than_hours: int) -> dict[str, int]`:
    1. Compute `cutoff = utcnow() - timedelta(hours=older_than_hours)`.
    2. Query `ocr_queue_items_collection.find({"createdAt": {"$lt": cutoff}}, {"imagePath": 1, "fileId": 1})`.
    3. For each, attempt `image_store.delete_path(imagePath)` if present; else `fs.delete(fileId)` if present.
    4. `delete_many({"createdAt": {"$lt": cutoff}})` for the items.
    5. Final sweep `image_store.prune_older_than(older_than_hours * 3600)` to catch orphans whose row was already deleted.
    6. Return `{filesDeleted, itemsDeleted, orphanFilesDeleted, errors}`.
- `backend/controllers/internal_jobs_controller.py`
  - New route `POST /api/internal/jobs/prune-staged-images` mirroring the existing weekly-summary pattern: validates internal token, parses optional `olderThanHours` (defaults to `IMAGE_RETENTION_HOURS`), calls `prune_staged_images`, returns counts.
- `scheduler/config.py`
  - Parse second cron `IMAGE_PRUNE_CRON` (default `"0 3 * * *"`). Keep existing `SCHEDULER_CRON` untouched.
- `scheduler/main.py`
  - `last_processed_minute` becomes `dict[str, str]` keyed by job name (`"weekly_summary"`, `"image_prune"`).
  - Each tick: for each `(job_name, schedule, action)` triple, dedupe + run.
  - `action` for image prune: `client.trigger_image_prune(scheduler_token=...)`.
- `scheduler/client.py`
  - New `trigger_image_prune(scheduler_token: str) -> dict`: `POST /api/internal/jobs/prune-staged-images` with the standard internal-token header. No body; backend uses default retention.

Implementation notes
- Single-tick concurrency: the existing tick loop is single-threaded. Two jobs at the same minute boundary will both run sequentially. Acceptable.
- The orphan sweep at the end of `prune_staged_images` makes the contract idempotent: even if a row was deleted by hand and the file was orphaned, it'll get cleaned within 24h.

Unit tests (phase-local)
- `backend/tests/unit/test_image_pruner.py`
  - `test_prune_deletes_old_files_and_items`
  - `test_prune_keeps_fresh_items_and_files`
  - `test_prune_handles_missing_files_gracefully`
  - `test_prune_orphan_sweep_catches_files_without_rows`
- `scheduler/tests/test_main.py` (new or extended)
  - `test_two_jobs_dedupe_independently_in_same_tick`
  - `test_image_prune_only_fires_at_03_00_local`

---

## Phase 4: Compose volume + docs
Affected files and changes
- `docker-compose.yml`
  - Backend service: add `volumes: - mail-images:/var/lib/avenu/images`; add `IMAGE_STORE_DIR`, `IMAGE_RETENTION_HOURS`, `FEATURE_OCR_AUTO_EXTRACT` to `environment`.
  - Scheduler service: add `IMAGE_PRUNE_CRON` to `environment`.
  - Top-level `volumes: { mail-images: { driver: local } }` (default named volume for dev).
- `docker-compose-prod.yml`
  - Same as above, plus `mail-images` configured with `driver_opts: { type: none, o: bind, device: ${MAIL_IMAGES_DIR:-/mnt/Main/other/AvenuMailImages/} }` to match the Prometheus pattern.
- `docs/01-architecture/diagrams/data-model.mmd`
  - Add `string imagePath "optional, relative to IMAGE_STORE_DIR"` to `OCR_QUEUE_ITEM`.
