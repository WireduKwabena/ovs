"""Tests for ai_ml_services.monitoring.model_monitor."""

from __future__ import annotations

from django.test import SimpleTestCase

from ai_ml_services.monitoring.model_monitor import ModelMonitor


class TestModelMonitor(SimpleTestCase):
    def test_disabled_monitor_returns_disabled_status(self):
        monitor = ModelMonitor(enabled=False, use_redis=False)
        monitor.log_prediction("ok", 0.9, 0.2)
        monitor.log_error("X", "Y")

        metrics = monitor.get_metrics("auth")
        drift = monitor.check_data_drift("auth")

        self.assertEqual(metrics["status"], "disabled")
        self.assertFalse(drift["drift_detected"])

    def test_in_memory_window_and_metrics(self):
        monitor = ModelMonitor(enabled=True, use_redis=False, window_size=3)

        monitor.log_prediction("p1", 0.95, 0.3, model_name="fraud")
        monitor.log_prediction("p2", 0.90, 0.4, model_name="fraud")
        monitor.log_prediction("p3", 0.85, 0.5, model_name="fraud")
        monitor.log_prediction("p4", 0.80, 0.6, model_name="fraud")

        metrics = monitor.get_metrics("fraud")
        self.assertEqual(metrics["backend"], "memory")
        self.assertEqual(metrics["total_predictions"], 3)
        self.assertAlmostEqual(metrics["min_confidence"], 0.80, places=6)
        self.assertAlmostEqual(metrics["max_confidence"], 0.90, places=6)

    def test_drift_detection_in_memory(self):
        monitor = ModelMonitor(
            enabled=True,
            use_redis=False,
            drift_window_size=3,
            drift_threshold=0.15,
        )

        for conf in [0.95, 0.94, 0.93, 0.72, 0.71, 0.70]:
            monitor.log_prediction("pred", conf, 0.2, model_name="auth")

        drift = monitor.check_data_drift("auth")
        self.assertTrue(drift["drift_detected"])
