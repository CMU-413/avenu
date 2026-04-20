from __future__ import annotations

from prometheus_client import Counter

member_dashboard_views_total = Counter(
    "member_dashboard_views_total",
    "Successful member dashboard mail summary loads (GET /api/member/mail)",
)
