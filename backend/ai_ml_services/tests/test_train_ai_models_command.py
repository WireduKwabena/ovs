"""Tests for train_ai_models command behavior."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from ai_ml_services.commands.train_ai_models import Command


@override_settings(BASE_DIR="C:/Project Setup/Django/OVS-Redo/backend")
class TrainAIModelsCommandTests(SimpleTestCase):
    def test_dry_run_reports_paths(self):
        with TemporaryDirectory() as tmp_dir:
            model_root = Path(tmp_dir) / "models"
            model_root.mkdir(parents=True, exist_ok=True)
            workspace = Path(tmp_dir) / "workspace"
            with override_settings(
                AI_ML_AUTHENTICITY_MODEL_PATH=str(model_root / "authenticity_best.h5"),
                AI_ML_AUTHENTICITY_TORCH_MODEL_PATH=str(model_root / "authenticity_detector.pth"),
                AI_ML_FRAUD_MODEL_PATH=str(model_root / "fraud_classifier.pkl"),
            ):
                command = Command()
                command.stdout = StringIO()
                command.handle(
                    dry_run=True,
                    seed=42,
                    auth_epochs=1,
                    tf_epochs=1,
                    batch_size=4,
                    num_workers=0,
                    target_authentic_images=4,
                    forgeries_per_image=1,
                    max_auth_samples=8,
                    fraud_samples=2000,
                    fraud_ratio=0.2,
                    device="cpu",
                    workspace=str(workspace),
                    keep_workspace=False,
                    freeze_backbone=True,
                    skip_authenticity=False,
                    skip_fraud=False,
                )
                output = command.stdout.getvalue()
                self.assertIn("Dry run successful.", output)
                self.assertIn("device=cpu", output)
                self.assertIn("h5_path=", output)
                self.assertIn("fraud_path=", output)

    def test_workspace_is_cleaned_when_not_kept(self):
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            model_root = Path(tmp_dir) / "models"
            model_root.mkdir(parents=True, exist_ok=True)

            with override_settings(
                AI_ML_AUTHENTICITY_MODEL_PATH=str(model_root / "authenticity_best.h5"),
                AI_ML_AUTHENTICITY_TORCH_MODEL_PATH=str(model_root / "authenticity_detector.pth"),
                AI_ML_FRAUD_MODEL_PATH=str(model_root / "fraud_classifier.pkl"),
            ):
                command = Command()
                command.stdout = StringIO()

                with patch.object(
                    Command,
                    "_train_authenticity_pytorch",
                    return_value={"val_f1": 0.5, "val_accuracy": 0.5, "best_epoch": 1},
                ), patch.object(
                    Command,
                    "_train_authenticity_tensorflow",
                    return_value={"val_accuracy": 0.5},
                ), patch.object(
                    Command,
                    "_train_fraud_model",
                    return_value={"f1": 0.8, "auc": 0.9, "accuracy": 0.85},
                ), patch.object(
                    Command,
                    "_prepare_authenticity_dataset",
                    return_value=(workspace / "metadata.csv", {"total_samples": 10}),
                ):
                    command.handle(
                        dry_run=False,
                        seed=42,
                        auth_epochs=1,
                        tf_epochs=1,
                        batch_size=4,
                        num_workers=0,
                        target_authentic_images=4,
                        forgeries_per_image=1,
                        max_auth_samples=8,
                        fraud_samples=2000,
                        fraud_ratio=0.2,
                        device="cpu",
                        workspace=str(workspace),
                        keep_workspace=False,
                        freeze_backbone=True,
                        skip_authenticity=False,
                        skip_fraud=False,
                    )

                self.assertFalse(workspace.exists())
