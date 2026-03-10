## 1. Purpose

The testing strategy exists to enforce architectural boundaries and prevent regression across:

* Persistence integrity
* Aggregation determinism
* Authorization boundaries
* Notification failure isolation

Testing is layered to match system architecture.

---

## 2. Test Layers

### 2.1 Unit Tests

Scope:

* Service-layer logic
* Aggregation logic
* Authorization checks
* Notification orchestration behavior (mocked providers)

Characteristics:

* Mock repositories and providers
* No external I/O
* Fast execution
* Coverage enforced (≥75%)

Validated invariants:

* FR-15–17 aggregation determinism
* QA-S1 mailbox access enforcement
* QA-R1 notification isolation semantics

Executed in CI via:

```
coverage run -m unittest discover -s tests -t .
coverage report --fail-under=75
```

Integration tests are excluded via environment guard.

---

### 2.2 Mongo Integration Tests

Scope:

* Repository behavior against real Mongo
* Weekly aggregation over real persisted documents
* Notification log persistence semantics

Characteristics:

* Real `mongo:6` container in CI
* Test database name must be `avenu_db_dev`
* Hard fail if DB_NAME != `avenu_db_dev`
* No Atlas usage
* Not included in coverage accounting

Validated invariants:

* FR-10 persistence guarantees
* FR-15–17 aggregation consistency
* QA-R1 log persistence integrity
* Backend → Mongo boundary correctness

Executed in CI via:

```
python -m unittest discover -s tests/integration -t .
```

Environment:

```
MONGO_URI=mongodb://localhost:27017/avenu_db_dev
DB_NAME=avenu_db_dev
RUN_MONGO_INTEGRATION=1
```

---

### 2.3 HTTP Boundary Integration Tests

Scope:

* Controller routing and middleware enforcement at runtime
* Mailbox authorization behavior at HTTP boundary
* Member dashboard aggregation consistency against persisted mail data
* Scheduler-to-backend contract for `POST /api/internal/jobs/weekly-summary`

Characteristics:

* Real Flask app factory and real repositories against `avenu_db_dev`
* Real HTTP requests via framework test client
* Mocked provider transport `send()` methods only
* No controller/service/repository mocking
* Not included in coverage accounting

Validated invariants:

* QA-S1 mailbox access boundary enforcement (401/403 + no unauthorized mutation)
* QA-R1 notification failure isolation on internal weekly summary job path
* QA-R3 dashboard/summary aggregation integrity through shared service path

Executed in CI via:

```
python -m unittest discover -s tests/integration -p "test_http_*.py" -t .
```

Environment:

```
MONGO_URI=mongodb://localhost:27017/avenu_db_dev
DB_NAME=avenu_db_dev
RUN_MONGO_INTEGRATION=1
FLASK_TESTING=true
```

---

## 3. Separation of Concerns

Unit tests validate logic.

Integration tests validate wiring and persistence boundary behavior.
HTTP integration tests specifically validate runtime controller/auth/internal-job boundaries.

They must remain:

* Independently executable
* Independently failing
* Independently observable in CI

Coverage applies only to unit tests.

---

## 4. Safety Constraints

The following are enforced:

* Integration tests must never connect to production Mongo.
* Integration tests must refuse to run unless DB_NAME == `avenu_db_dev`.
* CI must fail if either unit or integration job fails.
* Integration tests must not be silently skipped in the integration job.

---

## 5. Future Extensions

The following test layers may be added later:

* HTTP boundary integration tests (controller-level)
* External provider contract tests
* Health-check monitoring validation

These are intentionally out of scope for current milestone.
