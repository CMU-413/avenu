# Member API Endpoints — Explainer

This document describes the member-facing API endpoints introduced to support session hydration, dashboard aggregation, and notification preferences.

These endpoints are session-based and scoped to the currently authenticated user.

---

## 1. GET `/api/session/me`

### Purpose
Resolve the currently authenticated user from the session cookie.

This endpoint is the source of truth for:
- Admin vs member routing
- User identity in frontend state
- Default notification preference state

### Auth
- Requires valid session cookie
- Returns 401 if unauthenticated

### Response Shape

```json
{
  "id": "<userId>",
  "email": "user@example.com",
  "fullname": "Jane Doe",
  "isAdmin": false,
  "teamIds": ["<teamId>"],
  "emailNotifications": true
}
```

### Notes

* `emailNotifications` is the only public preference field for session hydration.
* Internal storage (for example `notifPrefs`) is intentionally hidden from clients.
* No sensitive fields exposed.

---

## 2. GET `/api/member/mail?start=YYYY-MM-DD&end=YYYY-MM-DD`

### Purpose

Return aggregated mail data for the logged-in member within a date range.

This endpoint powers the member dashboard summary view.

### Auth Rules

* Requires valid session
* Must derive mailboxes from session user
* Must enforce member scope
* Must not allow cross-user access
* Should enforce role-aware behavior (admin access handled separately)

### Query Parameters

* `start` (inclusive, ISO date string)
* `end` (inclusive, ISO date string)

Both are required.

### Response Shape

```json
{
  "start": "2026-02-16",
  "end": "2026-02-22",
  "mailboxes": [
    {
      "mailboxId": "<id>",
      "name": "Acme Corp",
      "type": "company",
      "days": [
        { "date": "2026-02-16", "letters": 0, "packages": 1 },
        { "date": "2026-02-17", "letters": 2, "packages": 0 }
      ]
    }
  ]
}
```

### Aggregation Rules

* Backend performs aggregation.
* Only mailboxes owned by the authenticated member.
* No raw atomic mail rows returned.
* Each `days` entry contains computed totals for that mailbox on that date.

### Design Rationale

* Prevents frontend from reimplementing aggregation logic.
* Reduces payload size.
* Keeps domain rules centralized in backend.

---

## 3. PATCH `/api/member/preferences`

### Purpose

Allow a member to toggle email notifications.

This endpoint updates notification preferences for the authenticated user only.

### Auth

* Requires valid session
* Applies only to current user

### Request Body

```json
{
  "emailNotifications": true
}
```

### Backend Behavior

* Map `emailNotifications` to internal `notifPrefs` representation.
* Do not expose enum or storage format to frontend.
* Persist updated preferences.

### Response Shape

```json
{
  "id": "<userId>",
  "emailNotifications": true
}
```

### Notes

* This endpoint abstracts internal preference storage.
* Frontend should treat this as the canonical source after update.

---

## 4. POST `/api/mail-requests`

### Purpose

Create an expected-mail declaration for the authenticated member.

### Auth

* Requires valid member session
* `memberId` is derived server-side from session user (`users._id`)

### Request Body

```json
{
  "mailboxId": "<ObjectId>",
  "expectedSender": "Sender Name",
  "description": "Expected package",
  "startDate": "2026-02-20",
  "endDate": "2026-02-25"
}
```

Rules:
* `mailboxId` must be a valid ObjectId string.
* At least one of `expectedSender` or `description` is required.
* If both `startDate` and `endDate` are present, `endDate >= startDate`.
* Member must be authorized for `mailboxId`.

### Success Response (`201`)

```json
{
  "id": "<mailRequestId>",
  "memberId": "<userObjectId>",
  "mailboxId": "<mailboxObjectId>",
  "expectedSender": "Sender Name",
  "description": "Expected package",
  "startDate": "2026-02-20",
  "endDate": "2026-02-25",
  "status": "ACTIVE",
  "createdAt": "2026-02-20T10:00:00+00:00",
  "updatedAt": "2026-02-20T10:00:00+00:00"
}
```

### Error Responses

* `400` missing sender+description, or invalid date window
* `403` mailbox access forbidden
* `422` invalid ObjectId/date formats

---

## 5. GET `/api/mail-requests`

### Purpose

List active expected-mail declarations for the authenticated member.

### Auth

* Requires valid member session
* Returns only records where `memberId == session user _id` and `status == ACTIVE`

### Response Shape (`200`)

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

Sort order:
* `createdAt DESC`

---

## 6. DELETE `/api/mail-requests/{id}`

### Purpose

Cancel an active expected-mail declaration owned by the authenticated member.

### Auth

* Requires valid member session
* Cancellation is scoped by `{ _id, memberId, status: "ACTIVE" }`

### Behavior

* Soft delete only (`status` transitions to `CANCELLED`)
* Implemented with single atomic update and active-status guard

### Success Response

* `204 No Content`

### Error Responses

* `404` when request does not exist, is not owned by member, or is already `CANCELLED`
* `400` invalid route id format
