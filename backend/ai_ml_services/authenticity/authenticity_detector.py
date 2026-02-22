"""Deep-learning authenticity detector wrapper."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict

import cv2
import numpy as np

logger = logging.getLogger(__name__)

try:
    from tensorflow import keras
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    keras = None


class AuthenticityDetector:
    """Predict document authenticity from image input."""

    def __init__(self, model_path: str | None = None):
        self.model_path = self._resolve_model_path(model_path)
        self.model = None
        self.input_shape = (224, 224, 3)
        self._load_model()

    @staticmethod
    def _resolve_model_path(model_path: str | None) -> Path:
        if model_path:
            return Path(model_path)
        try:
            from django.conf import settings

            default_path = getattr(
                settings,
                "AI_ML_AUTHENTICITY_MODEL_PATH",
                settings.MODEL_PATH / "authenticity_best.h5",
            )
            path = Path(str(default_path))
            if not path.is_absolute():
                path = Path(settings.BASE_DIR) / path
            return path
        except Exception:
            return Path("models/authenticity_best.h5")

    def _load_model(self) -> None:
        if keras is None:
            logger.warning(
                "TensorFlow/Keras is not installed. Authenticity model will run in fallback mode."
            )
            return
        if not self.model_path.exists():
            logger.warning("Authenticity model path does not exist: %s", self.model_path)
            return
        try:
            self.model = keras.models.load_model(str(self.model_path))
            logger.info("Authenticity model loaded from %s", self.model_path)
        except Exception as exc:
            logger.warning("Could not load authenticity model: %s", exc, exc_info=True)
            self.model = None

    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        resized = cv2.resize(image, (self.input_shape[0], self.input_shape[1]))
        if len(resized.shape) == 2:
            resized = cv2.cvtColor(resized, cv2.COLOR_GRAY2RGB)
        elif resized.shape[2] == 4:
            resized = cv2.cvtColor(resized, cv2.COLOR_BGRA2RGB)
        else:
            resized = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        normalized = resized.astype("float32") / 255.0
        return np.expand_dims(normalized, axis=0)

    def get_model_info(self) -> Dict:
        return {
            "loaded": self.model is not None,
            "framework": "tensorflow",
            "input_shape": self.input_shape,
            "model_path": str(self.model_path),
        }

    def _fallback_prediction(self, image: np.ndarray, reason: str) -> Dict:
        # Lightweight fallback: high noise/very low contrast tends to be suspicious.
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        contrast = float(np.std(gray))
        confidence = max(10.0, min(90.0, contrast))
        authenticity_score = max(40.0, min(85.0, 50.0 + (contrast - 32.0) * 0.5))
        return {
            "authenticity_score": round(authenticity_score, 2),
            "is_authentic": authenticity_score >= 50.0,
            "confidence": round(confidence, 2),
            "raw_prediction": round(authenticity_score / 100.0, 4),
            "mode": "fallback",
            "fallback_reason": reason,
        }

    def predict(self, image: np.ndarray) -> Dict:
        if image is None:
            raise ValueError("Image cannot be None.")

        if self.model is None:
            return self._fallback_prediction(image, reason="model_unavailable")

        try:
            img_batch = self.preprocess_image(image)
            prediction = float(self.model.predict(img_batch, verbose=0)[0][0])
            authenticity_score = prediction * 100.0
            confidence = abs(prediction - 0.5) * 200.0
            return {
                "authenticity_score": round(authenticity_score, 2),
                "is_authentic": prediction > 0.5,
                "confidence": round(confidence, 2),
                "raw_prediction": round(prediction, 6),
                "mode": "model",
            }
        except Exception as exc:
            logger.error("Authenticity prediction error: %s", exc, exc_info=True)
            return self._fallback_prediction(image, reason="prediction_error")
