import os
import time
import unittest

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")

from services.health_service import HealthService


class HealthServiceTests(unittest.TestCase):
    def test_check_dependencies_returns_stable_full_map(self):
        service = HealthService(
            checks={
                "mongo": lambda _timeout: "healthy",
                "graph": lambda _timeout: "healthy",
                "twilio": lambda _timeout: "healthy",
            }
        )

        result = service.check_dependencies()

        self.assertEqual(list(result.keys()), ["mongo", "graph", "twilio"])
        self.assertEqual(
            result,
            {
                "mongo": "healthy",
                "graph": "healthy",
                "twilio": "healthy",
            },
        )

    def test_unknown_status_is_normalized_to_error(self):
        service = HealthService(
            checks={
                "mongo": lambda _timeout: "healthy",
                "graph": lambda _timeout: "healthy",
                "twilio": lambda _timeout: "unknown-status",
            }
        )

        result = service.check_dependencies()

        self.assertEqual(result["twilio"], "error")
        self.assertEqual(set(result.values()), {"healthy", "error"})

    def test_dependency_failure_is_isolated(self):
        calls: list[str] = []

        def check_mongo(_timeout: float) -> str:
            calls.append("mongo")
            return "healthy"

        def check_graph(_timeout: float) -> str:
            calls.append("graph")
            return "misconfigured"

        def check_twilio(_timeout: float) -> str:
            calls.append("twilio")
            raise RuntimeError("boom")

        service = HealthService(
            checks={
                "mongo": check_mongo,
                "graph": check_graph,
                "twilio": check_twilio,
            }
        )

        result = service.check_dependencies()

        self.assertEqual(calls, ["mongo", "graph", "twilio"])
        self.assertEqual(result["mongo"], "healthy")
        self.assertEqual(result["graph"], "misconfigured")
        self.assertEqual(result["twilio"], "error")

    def test_timeout_exception_maps_to_unreachable(self):
        service = HealthService(
            checks={
                "mongo": lambda _timeout: "healthy",
                "graph": lambda _timeout: (_ for _ in ()).throw(TimeoutError("timed out")),
                "twilio": lambda _timeout: "healthy",
            }
        )

        result = service.check_dependencies()

        self.assertEqual(result["graph"], "unreachable")

    def test_total_deadline_marks_remaining_dependencies_unreachable(self):
        def slow_mongo(_timeout: float) -> str:
            time.sleep(0.03)
            return "healthy"

        service = HealthService(
            per_provider_timeout_seconds=1.0,
            total_timeout_seconds=0.02,
            checks={
                "mongo": slow_mongo,
                "graph": lambda _timeout: "healthy",
                "twilio": lambda _timeout: "healthy",
            },
        )

        result = service.check_dependencies()

        self.assertEqual(result["mongo"], "healthy")
        self.assertEqual(result["graph"], "unreachable")
        self.assertEqual(result["twilio"], "unreachable")
        self.assertEqual(list(result.keys()), ["mongo", "graph", "twilio"])

    def test_checkers_receive_capped_per_provider_timeout(self):
        received: dict[str, float] = {}

        def capture_timeout(name: str):
            def _checker(timeout_value: float) -> str:
                received[name] = timeout_value
                return "healthy"

            return _checker

        service = HealthService(
            per_provider_timeout_seconds=0.25,
            total_timeout_seconds=3.0,
            checks={
                "mongo": capture_timeout("mongo"),
                "graph": capture_timeout("graph"),
                "twilio": capture_timeout("twilio"),
            },
        )

        result = service.check_dependencies()

        self.assertTrue(all(value <= 0.25 for value in received.values()))
        self.assertEqual(set(result.values()), {"healthy"})


if __name__ == "__main__":
    unittest.main()
