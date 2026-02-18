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
