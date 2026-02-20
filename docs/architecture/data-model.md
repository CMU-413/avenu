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

### MAIL_REQUEST

Collection: `mail_requests`

Lifecycle states:
- `ACTIVE`
- `CANCELLED`

Fields:
- `_id: ObjectId`
- `memberId: ObjectId` (required, references `users._id`)
- `mailboxId: ObjectId` (required, references `mailboxes._id`)
- `expectedSender: string | null`
- `description: string | null`
- `startDate: string | null` (`YYYY-MM-DD`)
- `endDate: string | null` (`YYYY-MM-DD`)
- `status: "ACTIVE" | "CANCELLED"`
- `createdAt: datetime`
- `updatedAt: datetime`

Rules:
- `memberId` is always derived from authenticated session user and never from client input.
- At least one of `expectedSender` or `description` must be present.
- If both `startDate` and `endDate` are present, `endDate >= startDate`.
- Cancel is a soft delete implemented by status transition: `ACTIVE -> CANCELLED`.
- No linkage to `mail` records; this is declaration-only.

Indexes:

```js
db.mail_requests.createIndex({ memberId: 1, status: 1 })
db.mail_requests.createIndex({ mailboxId: 1, status: 1 })
db.mail_requests.createIndex({ status: 1 })
```
