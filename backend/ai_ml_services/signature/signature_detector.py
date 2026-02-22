"""Runtime detector for signature authenticity."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Union

import cv2
import joblib
import numpy as np

logger = logging.getLogger(__name__)


class SignatureAuthenticityDetector:
    """Predict whether a signature sample appears genuine or forged."""

    def __init__(self, model_path: str | None = None):
        self.model_path = self._resolve_model_path(model_path)
        self.pipeline = None
        self._load_model()

    @staticmethod
    def _resolve_model_path(model_path: str | None) -> Path:
        if model_path:
            return Path(model_path)
        try:
            from django.conf import settings

            configured = getattr(
                settings,
                "AI_ML_SIGNATURE_MODEL_PATH",
                settings.MODEL_PATH / "signature_authenticity.pkl",
            )
            path = Path(str(configured))
            if not path.is_absolute():
                path = Path(settings.BASE_DIR) / path
            return path
        except Exception:
            return Path("models/signature_authenticity.pkl")

    def _load_model(self) -> None:
        if not self.model_path.exists():
            logger.warning("Signature model artifact not found: %s", self.model_path)
            return
        try:
            data = joblib.load(self.model_path)
            self.pipeline = data["pipeline"] if isinstance(data, dict) else data
            logger.info("Signature model loaded from %s", self.model_path)
        except Exception as exc:
            logger.warning("Could not load signature model: %s", exc, exc_info=True)
            self.pipeline = None

    @staticmethod
    def _ensure_image(image_or_path: Union[str, Path, np.ndarray]) -> np.ndarray:
        if isinstance(image_or_path, np.ndarray):
            return image_or_path
        image = cv2.imread(str(image_or_path))
        if image is None:
            raise ValueError(f"Could not read image: {image_or_path}")
        return image

    @staticmethod
    def _fallback_prediction(image: np.ndarray, reason: str) -> Dict:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if float(binary.mean()) < 127.0:
            binary = cv2.bitwise_not(binary)
        ink_density = float((binary < 128).mean())

        # Typical signature ink coverage is sparse; very high/very low coverage is suspicious.
        score = 80.0 - min(55.0, abs(ink_density - 0.12) * 500.0)
        score = float(max(25.0, min(85.0, score)))
        confidence = float(min(90.0, 35.0 + abs(score - 50.0)))
        return {
            "authenticity_score": round(score, 2),
            "is_authentic": score >= 55.0,
            "confidence": round(confidence, 2),
            "raw_prediction": round(score / 100.0, 6),
            "mode": "fallback",
            "fallback_reason": reason,
        }

    def predict(self, image_or_path: Union[str, Path, np.ndarray]) -> Dict:
        from ai_ml_services.signature.features import extract_signature_features

        image = self._ensure_image(image_or_path)
        if self.pipeline is None:
            return self._fallback_prediction(image, reason="model_unavailable")

        try:
            features = extract_signature_features(image).reshape(1, -1)
            if hasattr(self.pipeline, "predict_proba"):
                probability = float(self.pipeline.predict_proba(features)[0, 1])
            else:
                probability = float(self.pipeline.predict(features)[0])
            authenticity_score = probability * 100.0
            confidence = abs(probability - 0.5) * 200.0
            return {
                "authenticity_score": round(authenticity_score, 2),
                "is_authentic": probability >= 0.5,
                "confidence": round(confidence, 2),
                "raw_prediction": round(probability, 6),
                "mode": "model",
            }
        except Exception as exc:
            logger.error("Signature prediction failed: %s", exc, exc_info=True)
            return self._fallback_prediction(image, reason="prediction_error")

    def get_model_info(self) -> Dict:
        return {
            "loaded": self.pipeline is not None,
            "framework": "scikit-learn",
            "model_path": str(self.model_path),
        }
