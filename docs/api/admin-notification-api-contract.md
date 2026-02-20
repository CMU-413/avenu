# Admin API Contract

Internal scheduler endpoint note:
- `POST /api/internal/jobs/weekly-summary` is intentionally excluded from this document because it is an internal service-to-service endpoint (Scheduler -> Backend), not a public/admin user-facing API.

## 1. POST `/api/admin/notifications/special`

Triggers a predefined special-case notification for a specific member and mailbox.

### Request Body

```json
{
  "userId": "<ObjectId>"
}
```

### Behavior

- Requires admin session.
- Uses fixed template type: `mail-arrived`.
- `userId` is required.
- Returns notify result payload from `SpecialCaseNotifier`.

### Success Response (`200`)

```json
{
  "status": "sent",
  "channelResults": [
    {
      "channel": "email",
      "status": "sent",
      "messageId": "console-message-id"
    }
  ]
}
```

### Error Responses

- `401` unauthorized (missing session)
- `403` forbidden (non-admin session)
- `400` invalid object ids
- `422` missing required body fields

---

## 2. GET `/api/admin/mail-requests`

Returns active expected-mail declarations across all members.

### Auth

- Requires admin session.

### Query Params (optional)

- `mailboxId=<ObjectId string>`
- `memberId=<ObjectId string>` where `memberId` references `users._id` (not Optix ID)

### Behavior

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
