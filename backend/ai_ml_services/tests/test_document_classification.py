"""Tests for document classification runtime utilities."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import cv2
import joblib
import numpy as np
from django.test import SimpleTestCase
from sklearn.linear_model import SGDClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ai_ml_services.document_classification.classifier import DocumentTypeClassifier
from ai_ml_services.document_classification.features import DocumentFeatureExtractor


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
