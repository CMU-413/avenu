import json
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

SCHEDULER_ROOT = Path(__file__).resolve().parents[1]
if str(SCHEDULER_ROOT) not in sys.path:
    sys.path.insert(0, str(SCHEDULER_ROOT))

from client import BackendClient, BackendClientError


class _FakeResponse:
    def __init__(self, status: int, body: dict):
        self.status = status
        self._body = json.dumps(body).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class BackendClientTests(unittest.TestCase):
    def test_client_posts_to_backend_service_url(self):
        captured = {}

        def fake_urlopen(request, timeout=0):
            captured["url"] = request.full_url
            captured["method"] = request.get_method()
            captured["timeout"] = timeout
            return _FakeResponse(
                status=200,
                body={
                    "weekStart": "2026-02-09",
                    "weekEnd": "2026-02-15",
                    "processed": 1,
                    "sent": 1,
                    "skipped": 0,
                    "failed": 0,
                    "errors": 0,
                },
            )

        client = BackendClient("http://backend:8000")
        with patch("client.urllib.request.urlopen", side_effect=fake_urlopen):
            result = client.trigger_weekly_summary(
                scheduler_token="secret",
                week_start=date(2026, 2, 9),
                week_end=date(2026, 2, 15),
                idempotency_key="weekly-summary:2026-02-09",
            )

        self.assertEqual(captured["url"], "http://backend:8000/api/internal/jobs/weekly-summary")
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["timeout"], 10)
        self.assertEqual(result["sent"], 1)

    def test_client_sends_scheduler_auth_and_idempotency_headers(self):
        captured = {}

        def fake_urlopen(request, timeout=0):
            captured["scheduler_token"] = request.get_header("X-scheduler-token")
            captured["idempotency_key"] = request.get_header("Idempotency-key")
            captured["content_type"] = request.get_header("Content-type")
            payload = json.loads(request.data.decode("utf-8"))
            captured["payload"] = payload
            return _FakeResponse(status=200, body={"ok": True})

        client = BackendClient("http://backend:8000")
        with patch("client.urllib.request.urlopen", side_effect=fake_urlopen):
            client.trigger_weekly_summary(
                scheduler_token="scheduler-secret",
                week_start=date(2026, 2, 9),
                week_end=date(2026, 2, 15),
                idempotency_key="weekly-summary:2026-02-09",
            )

        self.assertEqual(captured["scheduler_token"], "scheduler-secret")
        self.assertEqual(captured["idempotency_key"], "weekly-summary:2026-02-09")
        self.assertEqual(captured["content_type"], "application/json")
        self.assertEqual(captured["payload"], {"weekStart": "2026-02-09", "weekEnd": "2026-02-15"})

    def test_client_treats_replayed_response_as_success(self):
        client = BackendClient("http://backend:8000")
        with patch(
            "client.urllib.request.urlopen",
            return_value=_FakeResponse(
                status=200,
                body={
                    "weekStart": "2026-02-09",
                    "weekEnd": "2026-02-15",
                    "processed": 4,
                    "sent": 3,
                    "skipped": 1,
                    "failed": 0,
                    "errors": 0,
                },
            ),
        ):
            result = client.trigger_weekly_summary(
                scheduler_token="scheduler-secret",
                week_start=date(2026, 2, 9),
                week_end=date(2026, 2, 15),
                idempotency_key="weekly-summary:2026-02-09",
            )
        self.assertEqual(result["skipped"], 1)

    def test_client_handles_non_2xx_with_structured_error(self):
        client = BackendClient("http://backend:8000")
        error = HTTPError(
            url="http://backend:8000/api/internal/jobs/weekly-summary",
            code=500,
            msg="server error",
            hdrs=None,
            fp=None,
        )
        error.read = lambda: b'{"error":"boom"}'
        with patch("client.urllib.request.urlopen", side_effect=error):
            with self.assertRaises(BackendClientError):
                client.trigger_weekly_summary(
                    scheduler_token="scheduler-secret",
                    week_start=date(2026, 2, 9),
                    week_end=date(2026, 2, 15),
                    idempotency_key="weekly-summary:2026-02-09",
                )


if __name__ == "__main__":
    unittest.main()
