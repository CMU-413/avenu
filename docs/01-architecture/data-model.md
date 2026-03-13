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
- One document = one piece of mail. No cumulative `count` field.
- `receiverName` and `senderInfo` are populated via OCR scan (Tesseract, self-hosted) and confirmed by admin before saving.
- Aggregated counts for dashboards are computed by counting documents.

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
- `status: "processing" | "completed" | "failed"`
- `totalCount: int`
- `completedCount: int`
- `createdAt: datetime`
- `updatedAt: datetime`

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
- `status: "pending" | "completed" | "failed" | "confirmed"`
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

