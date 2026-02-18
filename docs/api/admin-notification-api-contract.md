# Admin Notification API Contract

## 1. POST `/admin/notifications/special`

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
