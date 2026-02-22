# Task Checklist
## Phase 1
- ☐ Add shared data access, validation, error mapping, and idempotency primitives.
- ☐ Create/ensure MongoDB indexes (including global unique email index and FK-supporting indexes).
- ☐ Introduce request/response schema definitions and normalization rules for all models.

## Phase 2
- ☐ Implement `TEAM`/`MAIL` CRUD APIs and `MAILBOX` read/update APIs with relationship checks and minimal transaction boundaries.
- ☐ Enforce default `TEAM` delete restriction and admin-only prune flow (`pruneUsers=true`) in a transaction.
- ☐ Enforce mailbox ownership invariants and event-level `MAIL` idempotent ingest constraints.

## Phase 3
- ☐ Implement `USER` CRUD APIs with hard-delete semantics and global email uniqueness.
- ☐ Wire owner lifecycle hooks (implicit mailbox create on user/team create; mailbox cleanup on owner deletion).
- ☐ Add focused unit tests for validators, transactional integrity paths, idempotency, and delete semantics.

## Locked Decisions
- Delete strategy: **hard-delete for `USER`/`TEAM`/`MAILBOX`/`MAIL`**.
- `USER.email` uniqueness: global unique index.
- `TEAM` deletion: default `restrict`; optional admin-only prune (`DELETE /teams/{id}?pruneUsers=true`) that removes team membership from users, then deletes team.
- `MAIL` granularity: event-level records.
- `MAIL` identity: MongoDB `_id` only; no external ingestion key constraints.
- Mailbox lifecycle: mailbox is **implicitly created** with `USER`/`TEAM` creation and is strictly owner-bound.
- Direct mailbox deletion is removed from public API; any repair-only mailbox deletion is internal tooling only and only allowed after owner deletion.

## Phase 1: Foundation (Schemas, Indexes, Idempotency)
Affected files and changes
- `backend/config.py`: add collection handles for `teams`, `mailboxes`, `mail`, `idempotency_keys`; add index bootstrap function callable at startup.
- `backend/app.py`: register centralized request validation + error translation helpers (400/404/409/422).
- `backend/models.py` (new): define schema contracts and normalization for each entity.
- `backend/validators.py` (new): input validators (ObjectId parsing, enum checks, email/phone normalization, dedupe arrays).
- `backend/idempotency.py` (new): idempotency-key reservation and replay helpers.

### Collection contracts
- `users`: `_id`, `optixId`, `isAdmin`, `fullname`, `email`, `phone`, `teamIds[]`, `notifPrefs[]`, `createdAt`, `updatedAt`.
- `teams`: `_id`, `optixId`, `name`, `createdAt`, `updatedAt`.
- `mailboxes`: `_id`, `type` (`user|team`), `refId`, `displayName`, `createdAt`, `updatedAt`.
- `mail`: `_id`, `mailboxId`, `date`, `type` (`letter|package`), `count`, `createdAt`, `updatedAt`.
- `idempotency_keys`: `_id`, `key`, `route`, `method`, `requestHash`, `responseStatus`, `responseBody`, `createdAt`, `expiresAt`.

### Index plan
- `users`
  - unique: `{ optixId: 1 }`
  - unique: `{ email: 1 }`
  - multikey: `{ teamIds: 1 }`
- `teams`
  - unique: `{ optixId: 1 }`
  - optional lookup: `{ name: 1 }`
- `mailboxes`
  - unique compound: `{ type: 1, refId: 1 }`
  - lookup: `{ refId: 1 }`
- `mail`
  - query: `{ mailboxId: 1, date: -1 }`
- `idempotency_keys`
  - unique: `{ key: 1, route: 1, method: 1 }`
  - TTL: `{ expiresAt: 1 }`

### Validation rules
- Shared: reject unknown enum values; reject duplicate array elements where set semantics apply.
- `USER`: `optixId` positive int; `email` required + lowercase normalized; `teamIds` distinct ObjectIds; `notifPrefs` subset of `{email,text}`.
- `TEAM`: `optixId` positive int; `name` required non-empty string.
- `MAILBOX`: `type` required; `refId` required ObjectId; `displayName` required non-empty.
- `MAIL`: `mailboxId` required ObjectId; `date` required ISO datetime -> UTC; `count` int >= 1; `type` enum.

### Unit tests (phase-local)
- Index creation tests validate expected unique and supporting index definitions.
- Validator tests for success/failure normalization cases.
- Idempotency tests: first request stores result, retry with same body replays, retry with different body returns 409.

## Phase 2: TEAM / MAILBOX / MAIL APIs + Relationship Enforcement
Affected files and changes
- `backend/app.py`: add `TEAM`, `MAILBOX`, `MAIL` routes and route-level auth gates for admin-only paths.
- `backend/repositories.py` (new): isolate MongoDB operations and transaction-scoped helpers.
- `backend/services/team_service.py` (new): team business rules (restrict delete, prune workflow).
- `backend/services/mailbox_service.py` (new): mailbox ownership and lifecycle constraints.
- `backend/services/mail_service.py` (new): event-level mail create/update/query rules.

### RESTful endpoints
- `TEAM`
  - `POST /teams`
  - `GET /teams`
  - `GET /teams/{id}`
  - `PATCH /teams/{id}`
  - `DELETE /teams/{id}` (default restrict)
  - `DELETE /teams/{id}?pruneUsers=true` (admin-only)
- `MAILBOX`
  - `GET /mailboxes`
  - `GET /mailboxes/{id}`
  - `PATCH /mailboxes/{id}` (displayName only)
- `MAIL`
  - `POST /mail`
  - `GET /mail`
  - `GET /mail/{id}`
  - `PATCH /mail/{id}`
  - `DELETE /mail/{id}`

### Relationship enforcement
- `TEAM` delete default behavior (`restrict`): deny delete if any `users.teamIds` contains team `_id`.
- `TEAM` prune behavior (`pruneUsers=true`): in one transaction with fixed ordering, (1) `$pull` team id from all matching users, (2) delete team mailbox + mail, (3) delete team.
- `MAILBOX` create is internal-only during owner creation; owner existence is enforced in that transaction and owner identity (`type`, `refId`) is immutable afterward.
- `MAIL` create/update: check referenced mailbox exists.
- One-per-owner invariant: unique `{type, refId}` plus service guard preventing replacement mailbox while existing one is present.

### Transaction boundaries (only true multi-doc operations)
- Required transactions:
  - team create with implicit mailbox creation (`teams` + `mailboxes`)
  - team prune delete flow (`users` + `mailboxes` + `mail` + `teams`)
  - user create with implicit mailbox creation (`users` + `mailboxes`)
  - user delete cascade (`users` + `mailboxes` + `mail`)
- Non-transactional operations:
  - simple single-doc create/read/update/delete with no dependent writes

### Idempotency
- Apply idempotency keys to `POST /teams`, `POST /users`, `POST /mail`.
- `DELETE` endpoints are idempotent: repeated delete returns 204 if resource already absent.

### Unit tests (phase-local)
- `TEAM` restrict delete test (409 when referenced).
- `TEAM` create transaction test: no team persists if implicit mailbox creation fails.
- `TEAM` prune test ensures user membership removal + dependent mailbox/mail cleanup in one atomic success path.
- `MAILBOX` owner existence checks and one-per-owner conflict test.
- `MAIL` create idempotency via `Idempotency-Key` replay behavior.

## Phase 3: USER APIs + Hard-Delete Semantics
Affected files and changes
- `backend/app.py`: add/replace `USER` routes with schema validation and hard-delete behavior.
- `backend/services/user_service.py` (new): user creation/update/delete orchestration and team membership checks.
- `backend/services/mailbox_service.py`: add implicit mailbox creation hook for new users and owner-delete cleanup.
- `backend/tests/test_user_api.py` (new): user CRUD + referential checks.

### RESTful endpoints
- `POST /users`
- `GET /users`
- `GET /users/{id}`
- `PATCH /users/{id}`
- `DELETE /users/{id}` (hard-delete with mailbox/mail cascade)

### USER relationship enforcement
- Create/update with `teamIds`: verify all referenced teams exist before write.
- User create: implicit mailbox create in same transaction (`type=user`, `refId=user._id`).
- User delete: transactionally delete user mailbox + mail, then delete user.

### Idempotency
- `POST /users` requires `Idempotency-Key` support.
- Replayed `POST /users` returns stored response if payload hash matches; mismatch returns 409.
- `DELETE /users/{id}` remains idempotent (204 if already absent).

### Unit tests (phase-local)
- User create fails when any team id does not exist.
- User create transaction test: no user persists if implicit mailbox creation fails.
- User hard-delete removes user plus mailbox/mail cascade artifacts.
- Global email uniqueness conflict test.
- Implicit mailbox creation on user create.
- Idempotent create replay and conflict behavior.
