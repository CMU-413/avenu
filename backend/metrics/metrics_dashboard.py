from __future__ import annotations

from prometheus_client import Counter

dashboard_views_total = Counter(
    "dashboard_views_total",
    "Successful member dashboard mail summary loads (GET /api/member/mail)",
)
