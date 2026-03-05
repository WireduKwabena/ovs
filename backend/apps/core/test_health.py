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


class SystemHealthSchemaTests(TestCase):
    def test_system_health_endpoint_schema_contract(self):
        try:
            from drf_spectacular.generators import SchemaGenerator
        except ModuleNotFoundError:
            self.skipTest("drf-spectacular is not installed.")

        schema = SchemaGenerator().get_schema(request=None, public=True)
        self.assertIsNotNone(schema)

        path_item = schema["paths"]["/api/system/health/"]["get"]
        response_200 = path_item["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual(response_200["$ref"], "#/components/schemas/SystemHealthResponse")

        health_component = schema["components"]["schemas"]["SystemHealthResponse"]
        required_fields = set(health_component.get("required", []))
        self.assertTrue(
            {"status", "timestamp", "strict_runtime_checks", "checks", "failures"}.issubset(required_fields)
        )
