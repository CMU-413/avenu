## Optix Data Model

### User

```graphql
User {
  user_id: ID!        // number
  is_admin: Boolean
  fullname: String
  email: String
  phone: String
  teams: [Team]
}
```

### Team

```graphql
Team {
  team_id: ID!        // number
  name: String!
  users_count: Int!
  users: [User]
}
```

---

## Optix → MongoDB Entity Hydration

### Team Handling

If `teams` field in users is non-empty:

* Upsert each team first, keyed on `team_id`
* Then upsert the user with team references

This guarantees referential consistency during hydration.

### User Upsert (keyed on `optixId`)

```js
db.users.updateOne(
  { optixId: user_id },
  {
    $setOnInsert: {
      optixId: user_id,
      // other default fields from above
    }
  },
  { upsert: true }
)
```

---

## Uniqueness Invariants

```js
db.users.createIndex({ optixId: 1 }, { unique: true })
db.teams.createIndex({ optixId: 1 }, { unique: true })
```

---

## Application MongoDB Model

### MAIL

Collection: `mail`

Each document represents a single piece of mail (one letter or one package).
Counts are derived by counting documents per mailbox per date, not stored as a field.

Fields:
- `_id: ObjectId`
- `mailboxId: ObjectId` (required, references `mailboxes._id`)
- `date: datetime` (required, the day the mail was recorded)
- `type: "letter" | "package"` (required)
- `receiverName: string | null` (optional, extracted via OCR or entered manually)
- `senderInfo: string | null` (optional, sender name or return address)
- `createdAt: datetime`
- `updatedAt: datetime`

Rules:
- One document = one piece of mail. No cumulative `count` field in the current model.
- `receiverName` and `senderInfo` are populated via OCR scan (self-hosted) and confirmed by admin before saving.
- Aggregated counts for dashboards are computed by counting documents (or by summing legacy `count` until migrated).

**Legacy `count` — transition strategy.**

Canonical model is one-doc-per-piece: each `mail` document represents exactly one letter or package. Older documents may include `count: N` meaning `N` pieces of the same `type` for a mailbox/day. The system currently operates in a transitional state and is being moved off `count` in the following phases:

1. **Today (read-compatible).** All aggregations (`services/mail_legacy.legacy_mail_piece_count`, dashboard, weekly summaries) treat missing/absent `count` as `1`, and `count: N` as `N`. The model PATCH path (`build_mail_patch`) still accepts `count` for backward-compat with clients editing legacy rows.
2. **Migration.** Run `backend/scripts/migrate_mail_legacy_count.py` (dry-run by default, pass `--apply` to write). The script expands each legacy `count: N` doc into `N` single-piece docs and `$unset`s `count`. Run against staging, verify counts match pre/post, then run against prod during a quiet window.
3. **Stop writing `count`.** `build_mail_create` no longer emits `count`. The `POST /api/mail` admin-entry path with `count: N > 1` is handled at the service layer: `create_mail` expands to `N` single-piece inserts, preserving the one-doc-per-piece invariant for all new writes. `build_mail_patch` continues to accept `count` transitionally (see next step).
4. **Drop `count` entirely.** After the migration in step 2 is confirmed clean in prod: remove `count` handling from `build_mail_patch`, remove `legacy_mail_piece_count`, and replace summation helpers with `len(...)`. Add an explicit index on `(mailboxId, date)` with a migration script that asserts zero remaining docs have `count`.

Stopping condition for the transition: a single scripted query against prod returns `db.mail.count_documents({"count": {"$exists": true}})` = 0 twice, 24h apart. At that point step 4 is safe to merge.

Indexes:

```js
db.mail.createIndex({ mailboxId: 1, date: -1 })
```

---

### MAIL_REQUEST

Collection: `mail_requests`

Lifecycle states:
- `ACTIVE`
- `CANCELLED`
- `RESOLVED`

Fields:
- `_id: ObjectId`
- `memberId: ObjectId` (required, references `users._id`)
- `mailboxId: ObjectId` (required, references `mailboxes._id`)
- `expectedSender: string | null`
- `description: string | null`
- `startDate: string | null` (`YYYY-MM-DD`)
- `endDate: string | null` (`YYYY-MM-DD`)
- `status: "ACTIVE" | "CANCELLED" | "RESOLVED"`
- `resolvedAt: datetime | null`
- `resolvedBy: ObjectId | null` (references admin `users._id`)
- `lastNotificationStatus: "SENT" | "FAILED" | null`
- `lastNotificationAt: datetime | null`
- `createdAt: datetime`
- `updatedAt: datetime`

Rules:
- `memberId` is always derived from authenticated session user and never from client input.
- At least one of `expectedSender` or `description` must be present.
- If both `startDate` and `endDate` are present, `endDate >= startDate`.
- Cancel is a soft delete implemented by status transition: `ACTIVE -> CANCELLED`.
- Resolve is an operational transition implemented as `ACTIVE -> RESOLVED`.
- `CANCELLED` and `RESOLVED` are terminal lifecycle states.
- `resolvedAt` and `resolvedBy` must be set when `status == "RESOLVED"`.
- `lastNotificationStatus`/`lastNotificationAt` capture send outcome metadata for resolve/retry attempts and do not affect lifecycle transitions.
- No linkage to `mail` records; this is declaration-only.

Indexes:

```js
db.mail_requests.createIndex({ memberId: 1, status: 1 })
db.mail_requests.createIndex({ mailboxId: 1, status: 1 })
db.mail_requests.createIndex({ status: 1 })
```

---

### OCR_JOBS

Collection: `ocr_jobs`

Stores bulk OCR processing jobs. Admin uploads multiple images; OCR runs asynchronously.

Fields:
- `_id: ObjectId`
- `createdBy: ObjectId` (references `users._id`, admin who uploaded)
- `date: string` (YYYY-MM-DD, mail date for the batch)
- `status: "processing" | "processed" | "failed" | "audited"`
  - `processing`: worker running OCR on images
  - `processed`: worker finished all items; awaiting admin review
  - `audited`: admin has completed review of all items (terminal for successful jobs)
  - `failed`: worker errored before all items could be processed
- `totalCount: int`
- `completedCount: int`
- `createdAt: datetime`
- `updatedAt: datetime`

**Deployment:** Env `FEATURE_ADMIN_OCR` (default `false`) is the master switch: when `false`, `/api/ocr` and all bulk queue routes return 404. Set `FEATURE_ADMIN_OCR=true` to enable. Bulk queue is additionally gated by `FEATURE_OCR_QUEUE_V2` (default `false`); the API also requires `FEATURE_ADMIN_OCR=true`.

Indexes:

```js
db.ocr_jobs.createIndex({ createdBy: 1, createdAt: -1 })
```

---

### OCR_QUEUE_ITEMS

Collection: `ocr_queue_items`

Individual parsed mail items within an OCR job. Admin verifies OCR, assigns mailbox, confirms to create mail.

Fields:
- `_id: ObjectId`
- `jobId: ObjectId` (references `ocr_jobs._id`)
- `index: int` (order within job)
- `status: "pending" | "completed" | "failed" | "confirmed" | "deleted"`
  - `pending`: awaiting OCR worker
  - `completed`: OCR finished successfully; awaiting admin confirm
  - `failed`: OCR failed for this item
  - `confirmed`: admin confirmed; mail record created (`confirmedAt` set)
  - `deleted`: soft-deleted by admin (e.g. unusable image)
- `receiverName: string | null`
- `senderInfo: string | null`
- `type: "letter" | "package"`
- `rawText: string | null` (original OCR output)
- `error: string | null` (if OCR failed)
- `mailboxId: ObjectId | null` (assigned before confirm)
- `confirmedAt: datetime | null` (when mail was created)
- `createdAt: datetime`
- `updatedAt: datetime`

Indexes:

```js
db.ocr_queue_items.createIndex({ jobId: 1, index: 1 })
db.ocr_queue_items.createIndex({ status: 1 })
```

