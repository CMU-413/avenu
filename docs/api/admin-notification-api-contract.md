# Admin API Contract

Internal scheduler endpoint note:
- `POST /api/internal/jobs/weekly-summary` is intentionally excluded from this document because it is an internal service-to-service endpoint (Scheduler -> Backend), not a public/admin user-facing API.

## 1. GET `/api/admin/mail-requests`

Returns active expected-mail declarations across all members.

### Auth

- Requires admin session.

### Query Params (optional)

- `mailboxId=<ObjectId string>`
- `memberId=<ObjectId string>` where `memberId` references `users._id` (not Optix ID)

### Behavior

- Requires admin session.
- Always filters to `status == ACTIVE`.
- If `mailboxId` is provided, filter by mailbox.
- If `memberId` is provided, filter by member.

### Success Response (`200`)

```json
[
  {
    "id": "<mailRequestId>",
    "memberId": "<userObjectId>",
    "mailboxId": "<mailboxObjectId>",
    "expectedSender": "Sender Name",
    "description": null,
    "startDate": null,
    "endDate": null,
    "status": "ACTIVE",
    "createdAt": "2026-02-20T10:00:00+00:00",
    "updatedAt": "2026-02-20T10:00:00+00:00"
  }
]
```

### Error Responses

- `401` unauthorized (missing session)
- `403` forbidden (non-admin session)
- `422` invalid `mailboxId` or `memberId` ObjectId query value

---

## 2. POST `/api/admin/mail-requests/{id}/resolve`

Resolves one active expected-mail request and triggers a mail-arrived notification attempt via `SpecialCaseNotifier`.

### Auth

- Requires admin session.

### Behavior

- Only `ACTIVE` requests can be resolved.
- Performs lifecycle transition and notification attempt in one service workflow.
- Resolution remains committed even when notification dispatch fails.
- Notification attempts are logged in notification logs.
- Updates request notification outcome metadata:
  - `lastNotificationStatus: "SENT" | "FAILED" | null`
  - `lastNotificationAt: datetime | null`

### Success Response (`200`)

Returns the updated `MAIL_REQUEST` document.

```json
{
  "id": "<mailRequestId>",
  "memberId": "<userObjectId>",
  "mailboxId": "<mailboxObjectId>",
  "expectedSender": "Sender Name",
  "description": null,
  "startDate": null,
  "endDate": null,
  "status": "RESOLVED",
  "resolvedAt": "2026-02-20T12:00:00+00:00",
  "resolvedBy": "<adminUserObjectId>",
  "lastNotificationStatus": "SENT",
  "lastNotificationAt": "2026-02-20T12:00:01+00:00",
  "createdAt": "2026-02-18T10:00:00+00:00",
  "updatedAt": "2026-02-20T12:00:01+00:00"
}
```

### Error Responses

- `401` unauthorized (missing session)
- `403` forbidden (non-admin session)
- `404` mail request not found or not `ACTIVE`
- `400` invalid route id format

---

## 3. POST `/api/admin/mail-requests/{id}/retry-notification`

Retries notification dispatch for a resolved request without changing lifecycle state.

### Auth

- Requires admin session.

### Behavior

- Re-invokes `SpecialCaseNotifier` for request member.
- Does not change `status`, `resolvedAt`, or `resolvedBy`.
- Updates:
  - `lastNotificationStatus`
  - `lastNotificationAt`
  - `updatedAt`
- Returns updated request document.

### Success Response (`200`)

```json
{
  "id": "<mailRequestId>",
  "status": "RESOLVED",
  "lastNotificationStatus": "FAILED",
  "lastNotificationAt": "2026-02-20T12:10:00+00:00"
}
```

### Error Responses

- `401` unauthorized (missing session)
- `403` forbidden (non-admin session)
- `404` mail request not found
- `400` invalid route id format
