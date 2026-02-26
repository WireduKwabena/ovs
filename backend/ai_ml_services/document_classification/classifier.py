from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

import cv2
import joblib
import numpy as np

from ai_ml_services.document_classification.features import DocumentFeatureExtractor

logger = logging.getLogger(__name__)


class DocumentTypeClassifier:
    """Runtime wrapper for document-type classification artifacts."""

    def __init__(self, model_path: str | Path):
        self.model_path = Path(model_path)
        self.model = None
        self.classes: List[str] = []
        self.feature_extractor = DocumentFeatureExtractor()
        self.error: str | None = None
        self.available = False
        self._load()

    def _load(self) -> None:
        if not self.model_path.exists():
            self.error = "model_not_found"
            self.available = False
            return
        try:
            artifact = joblib.load(self.model_path)
            if isinstance(artifact, dict):
                self.model = artifact.get("model")
                self.classes = [str(item) for item in artifact.get("classes", [])]
                self.feature_extractor = DocumentFeatureExtractor.from_config(
                    artifact.get("feature_config")
                )
            else:
                self.model = artifact
                self.classes = [str(item) for item in getattr(self.model, "classes_", [])]
                self.feature_extractor = DocumentFeatureExtractor()

            if self.model is None:
                self.error = "model_missing_in_artifact"
                self.available = False
                return
            self.available = True
            self.error = None
        except Exception as exc:
            logger.warning("Failed to load document classifier from %s: %s", self.model_path, exc)
            self.error = str(exc)
            self.available = False

    @staticmethod
    def _as_scores(model: Any, feature_row: np.ndarray) -> tuple[list[str], np.ndarray]:
        classes = [str(item) for item in getattr(model, "classes_", [])]

        if hasattr(model, "predict_proba"):
            probs = model.predict_proba(feature_row)[0].astype(np.float32)
            return classes, probs

        if hasattr(model, "decision_function"):
            decision = np.asarray(model.decision_function(feature_row), dtype=np.float32)
            if decision.ndim == 2:
                logits = decision[0]
                logits = logits - np.max(logits)
                exp = np.exp(logits)
                probs = exp / (exp.sum() + 1e-8)
                return classes, probs.astype(np.float32)

            # Binary margin fallback.
            margin = float(decision[0]) if decision.ndim > 0 else float(decision)
            prob_pos = 1.0 / (1.0 + np.exp(-margin))
            if len(classes) == 2:
                return classes, np.asarray([1.0 - prob_pos, prob_pos], dtype=np.float32)
            return classes, np.asarray([prob_pos], dtype=np.float32)

        predicted = model.predict(feature_row)
        label = str(predicted[0])
        return [label], np.asarray([1.0], dtype=np.float32)

    def predict_image(self, image: np.ndarray, top_k: int = 3) -> Dict[str, Any]:
        if not self.available or self.model is None:
            return {
                "available": False,
                "model_path": str(self.model_path),
                "error": self.error or "classifier_unavailable",
            }

        feature = self.feature_extractor.extract_from_image(image)
        if feature is None:
            return {
                "available": True,
                "model_path": str(self.model_path),
                "error": "feature_extraction_failed",
            }

        feature_row = feature.reshape(1, -1)
        predicted = self.model.predict(feature_row)
        predicted_label = str(predicted[0])
        labels, scores = self._as_scores(self.model, feature_row)

        if labels and scores.size and len(labels) == len(scores):
            sorted_idx = np.argsort(scores)[::-1]
            top_idx = sorted_idx[: max(1, int(top_k))]
            top_items = [
                {"label": labels[idx], "score": round(float(scores[idx]), 6)} for idx in top_idx
            ]
            confidence = 0.0
            for idx, label in enumerate(labels):
                if label == predicted_label:
                    confidence = round(float(scores[idx]), 6)
                    break
        else:
            top_items = [{"label": predicted_label, "score": 1.0}]
            confidence = 1.0

        return {
            "available": True,
            "model_path": str(self.model_path),
            "predicted_label": predicted_label,
            "confidence": confidence,
            "top_k": top_items,
            "classes": self.classes or labels,
        }

    def predict_file(self, file_path: str | Path, top_k: int = 3) -> Dict[str, Any]:
        image_path = Path(file_path)
        image = cv2.imread(str(image_path))
        if image is None:
            return {
                "available": self.available,
                "model_path": str(self.model_path),
                "error": "image_unreadable",
                "file_path": str(image_path),
            }
        result = self.predict_image(image=image, top_k=top_k)
        result["file_path"] = str(image_path)
        return result
