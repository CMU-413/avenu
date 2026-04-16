# Open Questions
None.

# Task Checklist
## Phase 1
- ☑ Replace integration-test session bootstrap with a direct test-client session helper that works for both member and admin users.
- ☑ Remove assertions that depend on the public login route from HTTP integration tests.

## Phase 2
- ☑ Move eager application-service imports out of module scope in integration tests so discovery stays bound to the intended test env.
- ☑ Keep unit-test coverage focused on the public login route behavior instead of reusing it as integration harness setup.

## Phase 1: Session Bootstrap
Affected files and changes
- `backend/tests/integration/support.py`: add a helper that looks up the user by email and writes `user_id` into the Flask test session directly.
- `backend/tests/integration/test_http_authz_boundary.py`: replace login-route bootstrapping with the direct session helper.
- `backend/tests/integration/test_http_mail_dashboard_consistency.py`: replace admin/member login-route bootstrapping with the direct session helper.

### Inline unit tests
- No new unit tests; existing `backend/tests/unit/test_admin_session_auth.py` already covers the public `/api/session/login` contract.

## Phase 2: Discovery-Safe Imports
Affected files and changes
- `backend/tests/integration/test_http_mail_dashboard_consistency.py`: move `MailSummaryService` import into the test body so module import does not force application config resolution before the harness env is in place.

### Inline unit tests
- No new unit tests; change is limited to integration-test module loading behavior.
