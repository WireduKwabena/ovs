from __future__ import annotations

from django.test import TestCase, override_settings
from django.urls import reverse


class SystemHealthApiTests(TestCase):
    @override_settings(
        DEBUG=True,
        USE_REDIS=False,
        REDIS_URL="",
        CELERY_BROKER_URL="",
    )
    def test_health_endpoint_returns_ok_in_non_strict_mode(self):
        response = self.client.get(reverse("core-system-health"))
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertFalse(payload["strict_runtime_checks"])
        self.assertIn("database", payload["checks"])
        self.assertIn("redis", payload["checks"])
        self.assertIn("celery_broker", payload["checks"])

    @override_settings(
        DEBUG=False,
        USE_REDIS=True,
        REDIS_URL="redis://127.0.0.1:6399/0",
        CELERY_BROKER_URL="redis://127.0.0.1:6399/0",
    )
    def test_health_endpoint_reports_degraded_when_critical_dependency_fails(self):
        response = self.client.get(reverse("core-system-health"))
        self.assertEqual(response.status_code, 503)

        payload = response.json()
        self.assertEqual(payload["status"], "degraded")
        self.assertTrue(payload["strict_runtime_checks"])
        self.assertIn("redis", payload["failures"])
