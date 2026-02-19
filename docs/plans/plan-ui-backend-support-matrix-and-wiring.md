# UI/Backend Support Matrix + Wiring Plan

## Scope and assumptions
- UI surfaces reviewed: `Login`, `AdminDashboard`, `SearchMailbox`, `RecordEntry`, `MemberDashboard`, `NotificationSettings`.
- Current frontend uses local state + mock arrays in `frontend/src/lib/mock-data.ts` and `frontend/src/lib/store.ts`.
- Backend reviewed in `backend/app.py` + service/model layers.

## Phase 1 - Backend Support Matrix

| UI surface | Required backend interaction | Existing endpoint | Method | Current request shape | Current response shape | Support status |
|---|---|---|---|---|---|---|
| Login (admin) | Start authenticated session | `/api/session/login` | `POST` | `{ "email": string }` | `204 No Content` (session cookie set) | Partially supported: endpoint exists, but UI currently has no admin email input and no `me` endpoint to confirm who logged in. |
| Login (member) | Start member session | `/api/session/login` | `POST` | `{ "email": string }` | `204 No Content` | Partially supported: login itself exists, but current member picker depends on mock member list. No safe member-list endpoint for public login and no session identity response. |
| AdminDashboard | Fetch mail for selected day | `/api/mail?date=YYYY-MM-DD` | `GET` | Query: `date` (optional), `mailboxId` (optional ObjectId) | `[{ id, mailboxId, date(ISO), type: "letter"\|"package", count, createdAt, updatedAt }]` | Partially supported: backend returns atomic mail rows; UI expects per-mailbox aggregated `{letters, packages}`. Aggregation must remain frontend-side (or new backend summary endpoint). |
| AdminDashboard | Resolve mailbox name/type for display | `/api/mailboxes` | `GET` | none | `[{ id, type: "user"\|"team", refId, displayName, createdAt, updatedAt }]` | Partially supported: mailbox metadata exists, but UI uses `name` + `type: company/personal`; mapping is needed (`displayName -> name`, `team/user -> company/personal`). |
| SearchMailbox | Search mailboxes by mailbox name | `/api/mailboxes` | `GET` | none | mailbox list above | Partially supported: mailbox-name search can be wired immediately client-side. |
| SearchMailbox | Search mailboxes by member name | No single endpoint | — | — | — | Partially supported: possible only via client aggregation of `/api/users` + `/api/teams` + `/api/mailboxes`; no direct backend projection provides mailbox + member names. |
| SearchMailbox | Fetch users for member-name matching | `/api/users` | `GET` | none | `[{ id, optixId, isAdmin, fullname, email, phone, teamIds[], notifPrefs[], createdAt, updatedAt }]` | Partially supported: endpoint exists but admin-session protected; still usable for admin flow. |
| SearchMailbox | Fetch teams to map team mailboxes | `/api/teams` | `GET` | none | `[{ id, optixId, name, createdAt, updatedAt }]` | Fully supported for admin flow (no auth decorator currently). |
| RecordEntry | Create letter/package records | `/api/mail` | `POST` | Header: `Idempotency-Key`; body: `{ mailboxId, date(ISO-8601), type: "letter"\|"package", count >= 1 }` | `{ id, mailboxId, date, type, count, createdAt, updatedAt }` | Partially supported: backend model differs from UI form model (`letters` + `packages` in one submit). UI must split into up to 2 POSTs. |
| MemberDashboard | Load member’s mailbox list | No member-scoped endpoint | — | — | — | Unsupported for member role today: `/api/mailboxes` is admin-only. |
| MemberDashboard | Load member weekly mail summary | No member-scoped endpoint | — | — | — | Unsupported for member role today: `/api/mail` is admin-only and only supports single-day filter (no range summary contract). |
| NotificationSettings | Read current member notification preference | No member-scoped session identity/profile endpoint | — | — | — | Unsupported for member role today: cannot reliably resolve current member from session in frontend. |
| NotificationSettings | Update notification preference | `/api/users/<user_id>` | `PATCH` | `{ notifPrefs: string[] }` | updated user doc | Unsupported for member self-service: endpoint requires admin session; UI currently uses boolean `emailNotifications` while backend uses enum array `notifPrefs`. |

### Where filtering/aggregation currently happens
- `AdminDashboard` (`frontend/src/pages/admin/AdminDashboard.tsx`):
  - Frontend filters records by selected date.
  - Frontend aggregates rows by `mailboxId` into `letters/packages` totals.
- `SearchMailbox` (`frontend/src/pages/admin/SearchMailbox.tsx`):
  - Frontend search/filter (name/member text match) and company/personal grouping.
- `MemberDashboard` (`frontend/src/pages/member/MemberDashboard.tsx`):
  - Frontend computes week ranges and per-day/per-mailbox totals.
- Backend currently provides raw lists with limited filtering:
  - `/api/mail` supports `date` (single day) and optional `mailboxId`.
  - No backend summary/aggregation endpoint for day/week totals.
  - No member-scoped endpoints for member dashboard/settings.

## Phase 2 - Wiring & Gap Plan

## 1) What can be wired immediately (with current backend)
1. Admin daily dashboard data:
   - Wire `GET /api/mail?date=...` + `GET /api/mailboxes`.
   - Keep frontend aggregation by mailbox and mapping for display fields.
2. Admin mailbox selection/search:
   - Wire `GET /api/mailboxes` for baseline list.
   - Optionally enrich member-name search using `GET /api/users` + `GET /api/teams` + client join.
3. Record entry save:
   - Replace local `addRecord` with `POST /api/mail` calls.
   - For each submit: if `letters > 0`, post one `type=letter`; if `packages > 0`, post one `type=package`.
   - Generate/send unique `Idempotency-Key` per POST.
4. Session login/logout mechanics:
   - Wire login/logout to `/api/session/login` and `/api/session/logout` for admin flow first.

## 2) Dummy data/state to remove in wiring phase
- Remove imports/usage of:
  - `frontend/src/lib/mock-data.ts` (`mailboxes`, `members`, `initialRecords`).
  - `frontend/src/lib/store.ts` state slices for `records`, `members`, `addRecord`, `toggleNotifications` (or reduce store to auth/session UI state only).
- Replace local mock-derived projections with API-derived transformations in page-level query logic.

## 3) Unsupported items requiring backend work

### A) Member identity endpoint (required for member flows)
- Proposed endpoint: `/api/session/me`
- Method: `GET`
- Required request payload: none (session cookie)
- Required response shape:
  ```json
  {
    "id": "<userId>",
    "email": "user@example.com",
    "fullname": "Jane Doe",
    "isAdmin": false,
    "teamIds": ["<teamId>"],
    "notifPrefs": ["email"]
  }
  ```
- Why UI needs it:
  - Determine logged-in user after `204` login response.
  - Remove dependence on mock member selection data.

### B) Member mailbox + weekly summary endpoint
- Proposed endpoint: `/api/member/mail-summary`
- Method: `GET`
- Required request payload (query):
  - `weekStart=YYYY-MM-DD` (start of week in UTC)
- Required response shape:
  ```json
  {
    "weekStart": "2026-02-16",
    "weekEnd": "2026-02-22",
    "mailboxes": [
      {
        "mailboxId": "<id>",
        "name": "Autumn Q's Personal",
        "type": "personal",
        "days": [
          { "date": "2026-02-16", "letters": 0, "packages": 1 },
          { "date": "2026-02-17", "letters": 2, "packages": 0 }
        ]
      }
    ]
  }
  ```
- Why UI needs it:
  - Member dashboard currently requires mailbox-scoped, daily aggregated data for a week.
  - Current admin-only `/api/mail` + `/api/mailboxes` cannot be used by non-admin users.

### C) Member notification preferences self-service endpoint
- Proposed endpoint: `/api/member/preferences`
- Method: `PATCH`
- Required request payload:
  ```json
  { "emailNotifications": true }
  ```
  (Backend can map to `notifPrefs` internally: include/remove `"email"`.)
- Required response shape:
  ```json
  {
    "id": "<userId>",
    "emailNotifications": true,
    "notifPrefs": ["email", "text"]
  }
  ```
- Why UI needs it:
  - `NotificationSettings` toggle must persist for the logged-in member without admin privileges.

### D) Optional admin search projection endpoint (quality-of-life)
- Proposed endpoint: `/api/admin/mailboxes/search-index`
- Method: `GET`
- Required request payload: none
- Required response shape:
  ```json
  [
    {
      "mailboxId": "<id>",
      "name": "Acme Corp",
      "type": "company",
      "memberNames": ["Autumn Quigley"]
    }
  ]
  ```
- Why UI needs it:
  - Eliminates multi-request client joins for mailbox/member-name search.
  - Not strictly required for initial admin wiring (can be deferred).

## Recommended implementation sequence after approval
1. Wire admin-only flows first (`AdminDashboard`, `SearchMailbox`, `RecordEntry`, admin login/logout).
2. Remove mock arrays/store record mutations for wired admin surfaces.
3. Add member backend endpoints (`/api/session/me`, `/api/member/mail-summary`, `/api/member/preferences`).
4. Wire member dashboard/settings to new member endpoints and fully remove member mock data.
