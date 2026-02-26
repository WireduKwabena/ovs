"""Tests for train_ai_models command behavior."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import cv2
import numpy as np
from django.core.management.base import CommandError
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
                    forgery_types=["copy_move", "jpeg"],
                    copy_move_regions=2,
                    jpeg_quality_min=60,
                    jpeg_quality_max=70,
                    verify_forgery_determinism=True,
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
                self.assertIn("forgery_profile=copy_move,jpeg", output)

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
                ) as prepare_mock:
                    command.handle(
                        dry_run=False,
                        seed=42,
                        auth_epochs=1,
                        tf_epochs=1,
                        batch_size=4,
                        num_workers=0,
                        target_authentic_images=4,
                        forgeries_per_image=1,
                        forgery_types=["resampling", "jpeg"],
                        copy_move_regions=1,
                        jpeg_quality_min=55,
                        jpeg_quality_max=80,
                        verify_forgery_determinism=False,
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
                    self.assertEqual(prepare_mock.call_count, 1)
                    prepare_kwargs = prepare_mock.call_args.kwargs
                    self.assertEqual(prepare_kwargs["forgery_types"], ("resampling", "jpeg"))
                    self.assertEqual(prepare_kwargs["jpeg_quality_min"], 55)
                    self.assertEqual(prepare_kwargs["jpeg_quality_max"], 80)

                self.assertFalse(workspace.exists())

    def test_invalid_forgery_type_raises_command_error(self):
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
                with self.assertRaises(CommandError):
                    command.handle(
                        dry_run=True,
                        seed=42,
                        auth_epochs=1,
                        tf_epochs=1,
                        batch_size=4,
                        num_workers=0,
                        target_authentic_images=4,
                        forgeries_per_image=1,
                        forgery_types=["unknown_mode"],
                        copy_move_regions=1,
                        jpeg_quality_min=55,
                        jpeg_quality_max=80,
                        verify_forgery_determinism=False,
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

    def test_assert_forgery_determinism_succeeds_for_seeded_generation(self):
        with TemporaryDirectory() as tmp_dir:
            image_path = Path(tmp_dir) / "sample.png"
            image = np.full((96, 96, 3), 180, dtype=np.uint8)
            cv2.rectangle(image, (20, 20), (76, 76), (10, 10, 10), -1)
            cv2.imwrite(str(image_path), image)

            command = Command()
            command._assert_forgery_determinism(
                image_path=image_path,
                forgeries_per_image=3,
                forgery_types=("copy_move", "resampling", "jpeg"),
                copy_move_regions=2,
                jpeg_quality_min=65,
                jpeg_quality_max=65,
                seed=13,
            )

    def test_generate_forgeries_respects_type_offset_when_single_variant(self):
        image = np.zeros((32, 32, 3), dtype=np.uint8)
        copy_move_out = np.full((32, 32, 3), 11, dtype=np.uint8)
        resampling_out = np.full((32, 32, 3), 22, dtype=np.uint8)
        jpeg_out = np.full((32, 32, 3), 33, dtype=np.uint8)

        with patch(
            "ai_ml_services.commands.train_ai_models.ForgeryGenerator.copy_move_forgery",
            return_value=copy_move_out,
        ), patch(
            "ai_ml_services.commands.train_ai_models.ForgeryGenerator.resampling_forgery",
            return_value=resampling_out,
        ), patch(
            "ai_ml_services.commands.train_ai_models.ForgeryGenerator.jpeg_compression_attack",
            return_value=jpeg_out,
        ):
            first = Command._generate_forgeries_for_image(
                image=image,
                forgeries_per_image=1,
                forgery_types=("copy_move", "resampling", "jpeg"),
                copy_move_regions=1,
                jpeg_quality_min=70,
                jpeg_quality_max=70,
                seed=7,
                type_offset=0,
            )[0]
            second = Command._generate_forgeries_for_image(
                image=image,
                forgeries_per_image=1,
                forgery_types=("copy_move", "resampling", "jpeg"),
                copy_move_regions=1,
                jpeg_quality_min=70,
                jpeg_quality_max=70,
                seed=8,
                type_offset=1,
            )[0]
            third = Command._generate_forgeries_for_image(
                image=image,
                forgeries_per_image=1,
                forgery_types=("copy_move", "resampling", "jpeg"),
                copy_move_regions=1,
                jpeg_quality_min=70,
                jpeg_quality_max=70,
                seed=9,
                type_offset=2,
            )[0]

        self.assertTrue(np.array_equal(first, copy_move_out))
        self.assertTrue(np.array_equal(second, resampling_out))
        self.assertTrue(np.array_equal(third, jpeg_out))
