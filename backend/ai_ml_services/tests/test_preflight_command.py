"""Tests for ai_ml_services preflight management command."""

from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from ai_ml_services.commands.check_ai_ml_services import Command


@override_settings(BASE_DIR="C:/Project Setup/Django/OVS-Redo/backend")
class TestAIMLPreflightCommand(SimpleTestCase):
    @patch.object(Command, "_scan_for_legacy_patterns", return_value=[])
    @patch.object(Command, "_check_required_imports", return_value=[])
    @patch.object(Command, "_check_runtime_configuration", return_value=([], []))
    @patch.object(Command, "_check_dependency_compatibility", return_value=([], []))
    @patch.object(Command, "_check_model_artifacts", return_value=["missing model"])
    @patch.object(Command, "_check_model_manifest", return_value=([], []))
    @patch.object(Command, "_check_model_quality", return_value=([], []))
    @patch.object(Command, "_check_syntax", return_value=[])
    def test_default_mode_allows_warnings(
        self,
        _syntax,
        _quality,
        _manifest,
        _artifacts,
        _deps,
        _runtime,
        _imports,
        _legacy,
    ):
        cmd = Command()
        cmd.stdout = StringIO()
        cmd.handle(strict=False)

    @patch.object(Command, "_scan_for_legacy_patterns", return_value=[])
    @patch.object(Command, "_check_required_imports", return_value=[])
    @patch.object(Command, "_check_runtime_configuration", return_value=([], []))
    @patch.object(Command, "_check_dependency_compatibility", return_value=([], []))
    @patch.object(Command, "_check_model_artifacts", return_value=["missing model"])
    @patch.object(Command, "_check_model_manifest", return_value=([], []))
    @patch.object(Command, "_check_model_quality", return_value=([], []))
    @patch.object(Command, "_check_syntax", return_value=[])
    def test_strict_mode_fails_on_warnings(
        self,
        _syntax,
        _quality,
        _manifest,
        _artifacts,
        _deps,
        _runtime,
        _imports,
        _legacy,
    ):
        cmd = Command()
        cmd.stdout = StringIO()
        with self.assertRaises(CommandError):
            cmd.handle(strict=True)

    @patch.object(Command, "_scan_for_legacy_patterns", return_value=[])
    @patch.object(Command, "_check_required_imports", return_value=["bad import"])
    @patch.object(Command, "_check_runtime_configuration", return_value=(["bad config"], []))
    @patch.object(Command, "_check_dependency_compatibility", return_value=([], []))
    @patch.object(Command, "_check_model_artifacts", return_value=[])
    @patch.object(Command, "_check_model_manifest", return_value=([], []))
    @patch.object(Command, "_check_model_quality", return_value=([], []))
    @patch.object(Command, "_check_syntax", return_value=[])
    def test_fails_when_errors_present(
        self,
        _syntax,
        _quality,
        _manifest,
        _artifacts,
        _deps,
        _runtime,
        _imports,
        _legacy,
    ):
        cmd = Command()
        cmd.stdout = StringIO()
        with self.assertRaises(CommandError):
            cmd.handle(strict=False)
