import os
import unittest
from unittest.mock import patch

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("FLASK_TESTING", "1")

from app import create_app


class HealthControllerTests(unittest.TestCase):
    def setUp(self):
        app = create_app(testing=True, ensure_db_indexes_on_startup=False, secret_key="test-secret")
        self.client = app.test_client()

    def test_liveness_route_returns_ok(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})

    def test_dependencies_route_returns_200_when_all_healthy(self):
        with patch(
            "controllers.health_controller.HealthService.check_dependencies",
            return_value={
                "mongo": "healthy",
                "optix": "healthy",
                "graph": "healthy",
                "twilio": "healthy",
            },
        ):
            response = self.client.get("/api/health/dependencies")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {
                "mongo": "healthy",
                "optix": "healthy",
                "graph": "healthy",
                "twilio": "healthy",
            },
        )

    def test_dependencies_route_returns_503_when_any_unhealthy(self):
        with patch(
            "controllers.health_controller.HealthService.check_dependencies",
            return_value={
                "mongo": "healthy",
                "optix": "unreachable",
                "graph": "healthy",
                "twilio": "healthy",
            },
        ):
            response = self.client.get("/api/health/dependencies")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.get_json(),
            {
                "mongo": "healthy",
                "optix": "unreachable",
                "graph": "healthy",
                "twilio": "healthy",
            },
        )

    def test_dependencies_route_always_returns_full_map(self):
        with patch(
            "controllers.health_controller.HealthService.check_dependencies",
            return_value={"mongo": "healthy"},
        ):
            response = self.client.get("/api/health/dependencies")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.get_json(),
            {
                "mongo": "healthy",
                "optix": "unreachable",
                "graph": "unreachable",
                "twilio": "unreachable",
            },
        )


if __name__ == "__main__":
    unittest.main()
