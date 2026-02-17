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

## 2. GET `/api/member/mail?from=YYYY-MM-DD&to=YYYY-MM-DD`

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

* `from` (inclusive, ISO date string)
* `to` (inclusive, ISO date string)

Both are required.

### Response Shape

```json
{
  "from": "2026-02-15",
  "to": "2026-02-21",
  "mailboxes": [
    {
      "mailboxId": "<id>",
      "name": "Acme Corp",
      "type": "company",
      "days": [
        { "date": "2026-02-15", "letters": 0, "packages": 1 },
        { "date": "2026-02-16", "letters": 2, "packages": 0 }
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
