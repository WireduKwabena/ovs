from pathlib import Path

from django.test import SimpleTestCase

from ai_ml_services.utils.paths import resolve_settings_path


class ResolveSettingsPathTests(SimpleTestCase):
    def test_relative_path_is_resolved_from_base_dir(self):
        resolved = resolve_settings_path(
            "models/fraud_classifier.pkl",
            base_dir=Path("/app/backend"),
            fallback_dir=Path("/app/backend/models"),
        )
        self.assertEqual(resolved, Path("/app/backend/models/fraud_classifier.pkl"))

    def test_windows_absolute_path_rebases_to_fallback_dir_filename(self):
        resolved = resolve_settings_path(
            r"A:\projects\Django\OVS-Redo\backend\models\rvl_cdip_classifier.pth",
            base_dir=Path("/app/backend"),
            fallback_dir=Path("/app/backend/models"),
        )
        self.assertEqual(resolved, Path("/app/backend/models/rvl_cdip_classifier.pth"))

    def test_stale_backend_prefixed_path_rebases_to_base_dir(self):
        resolved = resolve_settings_path(
            r"C:\old\machine\backend\models\midv500_classifier.pkl",
            base_dir=Path("/app/backend"),
            fallback_dir=Path("/app/backend/models"),
        )
        self.assertEqual(resolved, Path("/app/backend/models/midv500_classifier.pkl"))
