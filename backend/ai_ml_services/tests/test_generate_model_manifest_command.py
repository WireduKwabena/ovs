"""Tests for generate_model_manifest command behavior."""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from ai_ml_services.commands.generate_model_manifest import Command


def _write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


@override_settings(BASE_DIR="C:/Project Setup/Django/OVS-Redo/backend")
class GenerateModelManifestCommandTests(SimpleTestCase):
    def test_generates_manifest_for_existing_artifacts(self):
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            output_path = root / "model_manifest.json"

            auth_h5 = root / "authenticity_best.h5"
            fraud_pkl = root / "fraud_classifier.pkl"
            _write_bytes(auth_h5, b"auth-model")
            _write_bytes(fraud_pkl, b"fraud-model")

            missing_paths = {
                "AI_ML_AUTHENTICITY_TORCH_MODEL_PATH": str(root / "missing_auth.pt"),
                "AI_ML_SIGNATURE_MODEL_PATH": str(root / "missing_signature.pkl"),
                "AI_ML_RVL_CDIP_MODEL_PATH": str(root / "missing_rvl.pkl"),
                "AI_ML_MIDV500_MODEL_PATH": str(root / "missing_midv.pkl"),
            }

            with override_settings(
                AI_ML_MODEL_MANIFEST_PATH=str(output_path),
                AI_ML_AUTHENTICITY_MODEL_PATH=str(auth_h5),
                AI_ML_FRAUD_MODEL_PATH=str(fraud_pkl),
                **missing_paths,
            ):
                command = Command()
                command.stdout = StringIO()
                command.handle(
                    output=str(output_path),
                    model_version="",
                    strict=False,
                    include_missing=False,
                )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 1)
            models = payload["models"]
            self.assertEqual(len(models), 2)
            for entry in models:
                self.assertEqual(len(entry["sha256"]), 64)
                self.assertTrue(entry["version"])
                self.assertTrue(entry["trained_at"])

    def test_strict_mode_fails_when_configured_artifact_missing(self):
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            output_path = root / "model_manifest.json"
            only_model = root / "authenticity_best.h5"
            _write_bytes(only_model, b"auth-model")

            with override_settings(
                AI_ML_MODEL_MANIFEST_PATH=str(output_path),
                AI_ML_AUTHENTICITY_MODEL_PATH=str(only_model),
                AI_ML_AUTHENTICITY_TORCH_MODEL_PATH=str(root / "missing_auth.pt"),
                AI_ML_FRAUD_MODEL_PATH=str(root / "missing_fraud.pkl"),
                AI_ML_SIGNATURE_MODEL_PATH=str(root / "missing_signature.pkl"),
                AI_ML_RVL_CDIP_MODEL_PATH=str(root / "missing_rvl.pkl"),
                AI_ML_MIDV500_MODEL_PATH=str(root / "missing_midv.pkl"),
            ):
                command = Command()
                command.stdout = StringIO()
                with self.assertRaises(CommandError):
                    command.handle(
                        output=str(output_path),
                        model_version="",
                        strict=True,
                        include_missing=False,
                    )

    def test_include_missing_writes_placeholder_entries(self):
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            output_path = root / "model_manifest.json"
            auth_h5 = root / "authenticity_best.h5"
            _write_bytes(auth_h5, b"auth-model")
            missing_torch = root / "missing_auth.pt"

            with override_settings(
                AI_ML_MODEL_MANIFEST_PATH=str(output_path),
                AI_ML_AUTHENTICITY_MODEL_PATH=str(auth_h5),
                AI_ML_AUTHENTICITY_TORCH_MODEL_PATH=str(missing_torch),
                AI_ML_FRAUD_MODEL_PATH="",
                AI_ML_SIGNATURE_MODEL_PATH="",
                AI_ML_RVL_CDIP_MODEL_PATH="",
                AI_ML_MIDV500_MODEL_PATH="",
            ):
                command = Command()
                command.stdout = StringIO()
                command.handle(
                    output=str(output_path),
                    model_version="v1",
                    strict=False,
                    include_missing=True,
                )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["models"]), 2)
            missing_entry = next(
                entry
                for entry in payload["models"]
                if entry["setting"] == "AI_ML_AUTHENTICITY_TORCH_MODEL_PATH"
            )
            self.assertFalse(missing_entry.get("exists", True))
            self.assertEqual(missing_entry["version"], "v1")
            self.assertEqual(missing_entry["size_bytes"], 0)
