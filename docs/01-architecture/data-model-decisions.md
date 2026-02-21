## Data model

* **Why `mailbox.displayName`**
  It allows search results to be rendered directly from the mailbox collection without loading user or team entities, keeping the hottest path fast and branch-free. It is a derived, UI-facing cache that decouples search and rendering from relationship traversal.

* **Why we have a `MAILBOX` entity**
  Mailbox is the single interaction and ownership boundary for mail and search, collapsing users and teams into a uniform, queryable surface. This removes polymorphic mail ownership and makes search, navigation, and mail queries predictable and indexable.

* **Why `teamId` is embedded on the user side**
  The relationship is many-users-to-one-team and expansion is always user → team, so storing the foreign key on the user keeps reads simple and bounded. This avoids joins, matches MongoDB’s ownership model, and reflects the actual access pattern.
