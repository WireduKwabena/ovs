"""Tests for signature authenticity training/inference."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import importlib.util
import unittest

_HAS_SIGNATURE_DEPS = all(
    importlib.util.find_spec(dep) is not None
    for dep in ("cv2", "numpy", "pandas")
)

if _HAS_SIGNATURE_DEPS:
    import cv2
    import numpy as np
    import pandas as pd
else:  # pragma: no cover - optional ML extras
    cv2 = None
    np = None
    pd = None
from django.test import SimpleTestCase

if _HAS_SIGNATURE_DEPS:
    from ai_ml_services.signature.signature_detector import SignatureAuthenticityDetector
    from ai_ml_services.signature.train import train_signature_model


def _synthetic_signature(authentic: bool, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    canvas = np.full((180, 480, 3), 255, dtype=np.uint8)

    if authentic:
        x = np.linspace(20, 440, 14).astype(np.int32)
        y_base = 95 + rng.integers(-18, 18, size=x.shape[0])
        points = np.column_stack([x, y_base]).astype(np.int32)
        cv2.polylines(canvas, [points], isClosed=False, color=(20, 20, 20), thickness=2)
        cv2.line(canvas, (30, 130), (430, 130), (80, 80, 80), 1)
    else:
        cv2.putText(
            canvas,
            "FORGED",
            (70, 110),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.7,
            (15, 15, 15),
            3,
            cv2.LINE_AA,
        )
        cv2.rectangle(canvas, (60, 45), (420, 145), (120, 120, 120), 1)
    return canvas


_HAS_CV2_NUMPY = bool(cv2 is not None and np is not None and _HAS_SIGNATURE_DEPS)
_CV2_NUMPY_MISSING_REASON = "Optional dependency missing for signature tests: cv2/numpy"


@unittest.skipUnless(_HAS_CV2_NUMPY, _CV2_NUMPY_MISSING_REASON)
class SignatureModelTests(SimpleTestCase):
    def test_signature_detector_fallback_when_model_missing(self):
        detector = SignatureAuthenticityDetector(model_path="C:/nonexistent/signature.pkl")
        image = _synthetic_signature(authentic=True, seed=1)
        result = detector.predict(image)
        self.assertIn("authenticity_score", result)
        self.assertEqual(result["mode"], "fallback")

    def test_train_and_predict_signature_model(self):
        with TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            image_dir = tmp_root / "images"
            image_dir.mkdir(parents=True, exist_ok=True)

            rows = []
            total = 30
            for idx in range(total):
                authentic = idx % 2 == 0
                image = _synthetic_signature(authentic=authentic, seed=idx + 10)
                image_path = image_dir / f"sample_{idx:03d}.png"
                cv2.imwrite(str(image_path), image)
                rows.append(
                    {
                        "filename": image_path.name,
                        "filepath": str(image_path),
                        "label": "authentic" if authentic else "forged",
                        "split": "train" if idx < 24 else "val",
                    }
                )

            metadata_path = tmp_root / "metadata.csv"
            pd.DataFrame(rows).to_csv(metadata_path, index=False)
            model_path = tmp_root / "signature_authenticity.pkl"

            metrics = train_signature_model(
                metadata_path=metadata_path,
                output_path=model_path,
                seed=42,
                n_estimators=80,
            )
            self.assertTrue(model_path.exists())
            self.assertGreaterEqual(metrics["val_accuracy"], 0.0)
            self.assertGreaterEqual(metrics["val_f1"], 0.0)

            detector = SignatureAuthenticityDetector(model_path=str(model_path))
            result = detector.predict(_synthetic_signature(authentic=True, seed=999))
            self.assertEqual(result["mode"], "model")
            self.assertIn("is_authentic", result)
