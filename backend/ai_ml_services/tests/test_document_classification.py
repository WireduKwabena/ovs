"""Tests for document classification runtime utilities."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import importlib.util
import unittest

_HAS_DOCUMENT_CLASSIFIER_DEPS = all(
    importlib.util.find_spec(dep) is not None
    for dep in ("cv2", "numpy", "joblib", "torch", "sklearn")
)

if _HAS_DOCUMENT_CLASSIFIER_DEPS:
    import cv2
    import joblib
    import numpy as np
    import torch
    from sklearn.linear_model import SGDClassifier
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
else:  # pragma: no cover - optional ML extras
    cv2 = None
    joblib = None
    np = None
    torch = None
    SGDClassifier = Pipeline = StandardScaler = None
from django.test import SimpleTestCase

if _HAS_DOCUMENT_CLASSIFIER_DEPS:
    from ai_ml_services.document_classification.classifier import DocumentTypeClassifier
    from ai_ml_services.document_classification.features import DocumentFeatureExtractor


_HAS_CV2_NUMPY = bool(
    cv2 is not None and np is not None and _HAS_DOCUMENT_CLASSIFIER_DEPS
)
_CV2_NUMPY_MISSING_REASON = "Optional dependency missing for document classification tests: cv2/numpy"


@unittest.skipUnless(_HAS_CV2_NUMPY, _CV2_NUMPY_MISSING_REASON)
class DocumentTypeClassifierTests(SimpleTestCase):
    @staticmethod
    def _write_image(path: Path, pattern: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        canvas = np.full((128, 128, 3), 245, dtype=np.uint8)
        if pattern == "horizontal":
            for y in range(12, 120, 16):
                cv2.line(canvas, (8, y), (120, y), (20, 20, 20), 2)
        else:
            for x in range(12, 120, 16):
                cv2.line(canvas, (x, 8), (x, 120), (20, 20, 20), 2)
        cv2.imwrite(str(path), canvas)

    def test_classifier_predicts_from_file(self):
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            invoice = root / "invoice.png"
            resume = root / "resume.png"
            self._write_image(invoice, "horizontal")
            self._write_image(resume, "vertical")

            extractor = DocumentFeatureExtractor(image_size=128, hist_bins=32)
            X = np.asarray(
                [
                    extractor.extract_from_path(invoice),
                    extractor.extract_from_path(resume),
                ],
                dtype=np.float32,
            )
            y = np.asarray(["invoice", "resume"], dtype=object)

            model = Pipeline(
                steps=[
                    ("scaler", StandardScaler(with_mean=False)),
                    (
                        "clf",
                        SGDClassifier(
                            loss="log_loss",
                            max_iter=2000,
                            tol=1e-3,
                            random_state=42,
                        ),
                    ),
                ]
            )
            model.fit(X, y)

            model_path = root / "classifier.pkl"
            artifact = {
                "model": model,
                "classes": sorted(np.unique(y).tolist()),
                "feature_config": extractor.config(),
            }
            joblib.dump(artifact, model_path)

            classifier = DocumentTypeClassifier(model_path=model_path)
            prediction = classifier.predict_file(invoice)

            self.assertTrue(prediction["available"])
            self.assertIn(prediction["predicted_label"], {"invoice", "resume"})
            self.assertIn("top_k", prediction)

    def test_classifier_handles_missing_model(self):
        classifier = DocumentTypeClassifier(model_path="C:/missing/classifier.pkl")
        prediction = classifier.predict_file("C:/missing/image.png")
        self.assertFalse(prediction["available"])

    def test_classifier_loads_torch_artifact(self):
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            invoice = root / "invoice.png"
            resume = root / "resume.png"
            self._write_image(invoice, "horizontal")
            self._write_image(resume, "vertical")

            try:
                from torchvision import models as tv_models
            except ModuleNotFoundError:
                self.skipTest("torchvision not installed")

            try:
                model = tv_models.resnet18(weights=None)
            except TypeError:
                model = tv_models.resnet18(pretrained=False)
            model.fc = torch.nn.Linear(model.fc.in_features, 2)

            checkpoint_path = root / "rvl_classifier.pth"
            torch.save({"model_state_dict": model.state_dict()}, checkpoint_path)

            artifact_path = root / "rvl_classifier.pkl"
            joblib.dump(
                {
                    "model_type": "torch_resnet18_classifier",
                    "checkpoint_path": str(checkpoint_path),
                    "classes": ["invoice", "resume"],
                    "input_size": 224,
                    "normalization": {
                        "mean": [0.485, 0.456, 0.406],
                        "std": [0.229, 0.224, 0.225],
                    },
                },
                artifact_path,
            )

            classifier = DocumentTypeClassifier(model_path=artifact_path)
            prediction = classifier.predict_file(invoice)

            self.assertTrue(prediction["available"])
            self.assertEqual(prediction.get("model_kind"), "torch")
            self.assertIn(prediction["predicted_label"], {"invoice", "resume"})

    def test_classifier_loads_torch_artifact_with_windows_checkpoint_path(self):
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            invoice = root / "invoice.png"
            self._write_image(invoice, "horizontal")

            try:
                from torchvision import models as tv_models
            except ModuleNotFoundError:
                self.skipTest("torchvision not installed")

            try:
                model = tv_models.resnet18(weights=None)
            except TypeError:
                model = tv_models.resnet18(pretrained=False)
            model.fc = torch.nn.Linear(model.fc.in_features, 2)

            checkpoint_path = root / "rvl_classifier.pth"
            torch.save({"model_state_dict": model.state_dict()}, checkpoint_path)

            artifact_path = root / "rvl_classifier.pkl"
            # Simulate artifact produced on Windows then loaded in Linux runtime.
            joblib.dump(
                {
                    "model_type": "torch_resnet18_classifier",
                    "checkpoint_path": r"A:\projects\Django\OVS-Redo\backend\models\rvl_classifier.pth",
                    "classes": ["invoice", "resume"],
                    "input_size": 224,
                    "normalization": {
                        "mean": [0.485, 0.456, 0.406],
                        "std": [0.229, 0.224, 0.225],
                    },
                },
                artifact_path,
            )

            classifier = DocumentTypeClassifier(model_path=artifact_path)
            prediction = classifier.predict_file(invoice)

            self.assertTrue(prediction["available"])
            self.assertEqual(prediction.get("model_kind"), "torch")
            self.assertIn(prediction["predicted_label"], {"invoice", "resume"})
