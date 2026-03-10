"""Tests for runtime dataset components (forgery, fraud data, PyTorch loaders)."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import importlib.util
import unittest

_HAS_DATASET_RUNTIME_DEPS = all(
    importlib.util.find_spec(dep) is not None
    for dep in ("cv2", "numpy", "pandas")
)

if _HAS_DATASET_RUNTIME_DEPS:
    import cv2
    import numpy as np
    import pandas as pd
else:  # pragma: no cover - optional ML extras
    cv2 = None
    np = None
    pd = None
from django.test import SimpleTestCase

if _HAS_DATASET_RUNTIME_DEPS:
    from ai_ml_services.datasets.fraud_data_generator import FraudDatasetGenerator
    from ai_ml_services.datasets.generate_forgeries import ForgeryGenerator, generate_forgeries
    from ai_ml_services.datasets.pytorch_loaders import (
        DocumentAuthenticityDataset,
        create_data_loaders,
    )


_HAS_CV2_NUMPY = bool(cv2 is not None and np is not None and _HAS_DATASET_RUNTIME_DEPS)
_CV2_NUMPY_MISSING_REASON = "Optional dependency missing for dataset runtime tests: cv2/numpy"


@unittest.skipUnless(_HAS_CV2_NUMPY, _CV2_NUMPY_MISSING_REASON)
class ForgeryGeneratorRuntimeTests(SimpleTestCase):
    def test_copy_move_is_reproducible_with_seed(self):
        image = np.full((128, 128, 3), 160, dtype=np.uint8)
        cv2.rectangle(image, (20, 20), (100, 100), (10, 10, 10), -1)

        first = ForgeryGenerator(seed=7).copy_move_forgery(image, num_regions=2)
        second = ForgeryGenerator(seed=7).copy_move_forgery(image, num_regions=2)

        self.assertTrue(np.array_equal(first, second))

    def test_generate_forgeries_returns_expected_count(self):
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            input_dir = root / "auth"
            output_dir = root / "forged"
            input_dir.mkdir(parents=True, exist_ok=True)

            for idx in range(3):
                canvas = np.full((64, 64, 3), 200, dtype=np.uint8)
                cv2.putText(canvas, str(idx), (10, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (20, 20, 20), 2)
                cv2.imwrite(str(input_dir / f"doc_{idx}.png"), canvas)

            generated = generate_forgeries(
                input_dir=str(input_dir),
                output_dir=str(output_dir),
                num_per_image=2,
                forgery_types=("copy_move",),
                random_seed=11,
            )
            self.assertEqual(generated, 6)
            self.assertEqual(len(list(output_dir.glob("*.jpg"))), 6)


@unittest.skipUnless(_HAS_CV2_NUMPY, _CV2_NUMPY_MISSING_REASON)
class FraudDataGeneratorRuntimeTests(SimpleTestCase):
    def test_generate_application_data_is_reproducible(self):
        generator = FraudDatasetGenerator()
        train_a, test_a = generator.generate_application_data(
            n_samples=200,
            fraud_ratio=0.2,
            random_seed=19,
            test_size=0.25,
        )
        train_b, test_b = generator.generate_application_data(
            n_samples=200,
            fraud_ratio=0.2,
            random_seed=19,
            test_size=0.25,
        )

        self.assertTrue(train_a.equals(train_b))
        self.assertTrue(test_a.equals(test_b))
        self.assertGreater(train_a["is_fraud"].mean(), 0.0)
        self.assertLess(train_a["is_fraud"].mean(), 1.0)


@unittest.skipUnless(_HAS_CV2_NUMPY, _CV2_NUMPY_MISSING_REASON)
class PytorchLoaderRuntimeTests(SimpleTestCase):
    def _write_image(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        canvas = np.full((80, 120, 3), 220, dtype=np.uint8)
        cv2.rectangle(canvas, (10, 10), (110, 70), (25, 25, 25), 2)
        cv2.imwrite(str(path), canvas)

    def test_create_data_loaders_splits_when_val_missing(self):
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            files = []
            labels = ["authentic", "forged", "authentic", "forged", "authentic", "forged"]
            for idx, label in enumerate(labels):
                file_path = root / f"{label}_{idx}.png"
                self._write_image(file_path)
                files.append((file_path, label))

            metadata = pd.DataFrame(
                [
                    {
                        "filename": item[0].name,
                        "filepath": str(item[0]),
                        "label": item[1],
                        "split": "train",
                    }
                    for item in files
                ]
            )
            metadata_path = root / "metadata.csv"
            metadata.to_csv(metadata_path, index=False)

            train_loader, val_loader = create_data_loaders(
                metadata_file=str(metadata_path),
                batch_size=2,
                num_workers=0,
                random_seed=42,
            )

            self.assertGreater(len(train_loader.dataset), 0)
            self.assertGreater(len(val_loader.dataset), 0)

    def test_dataset_can_fail_on_missing_file(self):
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            missing_file = root / "missing.png"
            metadata = pd.DataFrame(
                [
                    {
                        "filename": "missing.png",
                        "filepath": str(missing_file),
                        "label": "authentic",
                    }
                ]
            )
            dataset = DocumentAuthenticityDataset(
                metadata_df=metadata,
                fail_on_missing=True,
            )
            with self.assertRaises(FileNotFoundError):
                _ = dataset[0]
