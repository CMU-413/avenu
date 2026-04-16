# Task Checklist

## Phase 1
- ☑ Document the controller session regression fix

## Phase 2
- ☑ Route Optix token login through the shared authenticated-session helper
- ☐ Run unit tests for the identity controller route

# Open Questions

- None.

## Phase 1

Affected files:
- `docs/02-plans/plan-fix-optix-token-session-regression.md`

Changes:
- Add an implementation-focused plan for repairing the Optix token session regression.

Inline unit tests:
- None.

## Phase 2

Affected files:
- `backend/controllers/identity_controller.py`
- `backend/tests/unit/test_identity_controller.py`

Changes:
- Replace direct session mutation in the Optix token route with the shared session establishment helper.
- Verify the existing controller unit tests cover the restored permanent session behavior and response codes.

Inline unit tests:
- `backend/tests/unit/test_identity_controller.py`
