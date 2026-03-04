from __future__ import annotations

import logging
import re
from pathlib import Path
from pathlib import PureWindowsPath
from typing import Any, Dict, List

import cv2
import joblib
import numpy as np

from ai_ml_services.document_classification.features import DocumentFeatureExtractor

logger = logging.getLogger(__name__)
WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")


class DocumentTypeClassifier:
    """Runtime wrapper for document-type classification artifacts."""

    def __init__(self, model_path: str | Path):
        self.model_path = Path(model_path)
        self.model = None
        self.classes: List[str] = []
        self.feature_extractor = DocumentFeatureExtractor()
        self.error: str | None = None
        self.available = False
        self.model_kind = "sklearn"

        self._torch = None
        self._torch_model = None
        self._torch_input_size = 224
        self._torch_mean = np.asarray([0.485, 0.456, 0.406], dtype=np.float32)
        self._torch_std = np.asarray([0.229, 0.224, 0.225], dtype=np.float32)

        self._load()

    def _resolve_checkpoint_path(self, raw_path: str | Path) -> Path:
        raw_text = str(raw_path or "").strip()
        path = Path(raw_text)
        if path.exists():
            return path

        # Windows absolute paths are not considered absolute on Linux/macOS.
        # When artifacts move between environments, fall back to checkpoint basename
        # colocated with the serialized classifier artifact.
        if WINDOWS_ABSOLUTE_PATH_RE.match(raw_text):
            win_name = PureWindowsPath(raw_text).name
            return (self.model_path.parent / win_name).resolve()

        if not path.is_absolute():
            return (self.model_path.parent / path).resolve()

        # Absolute path provided but not present in this runtime; try colocated basename.
        return (self.model_path.parent / path.name).resolve()

    def _load_torch_classifier_artifact(self, artifact: Dict[str, Any]) -> None:
        try:
            import torch
            from torchvision import models as tv_models
        except ModuleNotFoundError as exc:
            self.error = f"torch_runtime_missing: {exc}"
            self.available = False
            return

        classes = [str(item) for item in artifact.get("classes", [])]
        if not classes:
            self.error = "torch_artifact_missing_classes"
            self.available = False
            return

        raw_checkpoint = artifact.get("checkpoint_path") or str(self.model_path.with_suffix(".pth"))
        checkpoint_path = self._resolve_checkpoint_path(raw_checkpoint)
        if not checkpoint_path.exists():
            self.error = f"torch_checkpoint_not_found:{checkpoint_path}"
            self.available = False
            return

        try:
            checkpoint = torch.load(str(checkpoint_path), map_location="cpu")
        except Exception as exc:
            self.error = f"torch_checkpoint_load_failed:{exc}"
            self.available = False
            return

        state_dict = checkpoint.get("model_state_dict") if isinstance(checkpoint, dict) else checkpoint
        if state_dict is None:
            self.error = "torch_checkpoint_missing_state_dict"
            self.available = False
            return

        try:
            model = tv_models.resnet18(weights=None)
        except TypeError:
            model = tv_models.resnet18(pretrained=False)

        model.fc = torch.nn.Linear(model.fc.in_features, len(classes))
        incompat = model.load_state_dict(state_dict, strict=False)
        if incompat.missing_keys or incompat.unexpected_keys:
            logger.warning(
                "Loaded torch classifier with key mismatch (missing=%s unexpected=%s)",
                incompat.missing_keys,
                incompat.unexpected_keys,
            )

        model.eval()

        normalization = artifact.get("normalization") if isinstance(artifact, dict) else None
        mean = (normalization or {}).get("mean", [0.485, 0.456, 0.406])
        std = (normalization or {}).get("std", [0.229, 0.224, 0.225])

        self.classes = classes
        self.model_kind = "torch"
        self._torch = torch
        self._torch_model = model
        self._torch_input_size = int(artifact.get("input_size", 224) or 224)
        self._torch_mean = np.asarray(mean, dtype=np.float32)
        self._torch_std = np.asarray(std, dtype=np.float32)
        self.available = True
        self.error = None

    def _load(self) -> None:
        if not self.model_path.exists():
            self.error = "model_not_found"
            self.available = False
            return
        try:
            artifact = joblib.load(self.model_path)
            if isinstance(artifact, dict) and artifact.get("model_type") == "torch_resnet18_classifier":
                self._load_torch_classifier_artifact(artifact)
                return

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
            self.model_kind = "sklearn"
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

            margin = float(decision[0]) if decision.ndim > 0 else float(decision)
            prob_pos = 1.0 / (1.0 + np.exp(-margin))
            if len(classes) == 2:
                return classes, np.asarray([1.0 - prob_pos, prob_pos], dtype=np.float32)
            return classes, np.asarray([prob_pos], dtype=np.float32)

        predicted = model.predict(feature_row)
        label = str(predicted[0])
        return [label], np.asarray([1.0], dtype=np.float32)

    def _predict_torch(self, image: np.ndarray, top_k: int = 3) -> Dict[str, Any]:
        if self._torch is None or self._torch_model is None:
            return {
                "available": False,
                "model_path": str(self.model_path),
                "error": "torch_model_unavailable",
            }

        if image.ndim == 2:
            rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        elif image.shape[2] == 4:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGRA2RGB)
        else:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        resized = cv2.resize(rgb, (self._torch_input_size, self._torch_input_size), interpolation=cv2.INTER_AREA)
        arr = resized.astype(np.float32) / 255.0
        arr = (arr - self._torch_mean) / self._torch_std
        tensor = self._torch.from_numpy(arr.transpose(2, 0, 1)).to(self._torch.float32).unsqueeze(0)

        with self._torch.no_grad():
            logits = self._torch_model(tensor)
            probs = self._torch.softmax(logits, dim=1)[0].cpu().numpy().astype(np.float32)

        if not self.classes:
            labels = [str(idx) for idx in range(int(len(probs)))]
        else:
            labels = self.classes

        sorted_idx = np.argsort(probs)[::-1]
        top_idx = sorted_idx[: max(1, int(top_k))]
        top_items = [
            {"label": labels[idx], "score": round(float(probs[idx]), 6)} for idx in top_idx
        ]

        best_idx = int(top_idx[0])
        return {
            "available": True,
            "model_path": str(self.model_path),
            "predicted_label": labels[best_idx],
            "confidence": round(float(probs[best_idx]), 6),
            "top_k": top_items,
            "classes": labels,
            "model_kind": "torch",
        }

    def predict_image(self, image: np.ndarray, top_k: int = 3) -> Dict[str, Any]:
        if not self.available:
            return {
                "available": False,
                "model_path": str(self.model_path),
                "error": self.error or "classifier_unavailable",
            }

        if self.model_kind == "torch":
            return self._predict_torch(image=image, top_k=top_k)

        if self.model is None:
            return {
                "available": False,
                "model_path": str(self.model_path),
                "error": "classifier_unavailable",
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
            "model_kind": "sklearn",
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
