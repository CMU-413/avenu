from __future__ import annotations

import urllib.error
import urllib.request


class BackendClient:
    def __init__(self, base_url: str):
        self._base_url = base_url.rstrip("/")

    def check_health(self) -> tuple[bool, str]:
        request = urllib.request.Request(url=f"{self._base_url}/health", method="GET")
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                if response.status == 200:
                    return True, "ok"
                return False, f"unexpected-status-{response.status}"
        except urllib.error.URLError as exc:
            return False, str(exc)
