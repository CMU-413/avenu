"""Role constants for role-based access control."""

ROLE_ADMIN = "admin"
ROLE_MEMBER = "member"

VALID_ROLES = frozenset({ROLE_ADMIN, ROLE_MEMBER})
DEFAULT_ROLE = ROLE_MEMBER
