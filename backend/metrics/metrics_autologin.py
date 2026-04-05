from __future__ import annotations

from prometheus_client import Counter

autologin_success_total = Counter(
    "autologin_success_total",
    "Successful Optix token autologin (POST /api/optix-token completed with session)",
)

autologin_failed_total = Counter(
    "autologin_failed_total",
    "Failed Optix token autologin (missing token, sync error, or session error)",
)
