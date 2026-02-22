"""
Identity matching helpers for document-vs-interview verification.

Flow:
1. Extract candidate face from ID/passport document image (or PDF first page)
2. Extract best candidate face frame from interview video
3. Compute embeddings using FaceNet (preferred) or DeepFace fallback
4. Compute cosine similarity and classify against configured threshold
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

import cv2
import numpy as np
from django.conf import settings

try:
    import torch
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    torch = None

try:
    from facenet_pytorch import InceptionResnetV1, MTCNN
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    InceptionResnetV1 = None
    MTCNN = None

try:
    from deepface import DeepFace
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    DeepFace = None

try:
    from pdf2image import convert_from_path
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    convert_from_path = None

from ai_ml_services.utils.pdf import pdf2image_kwargs

logger = logging.getLogger(__name__)


class IdentityMatcher:
    """Document-face vs interview-face identity verification."""

    def __init__(
        self,
        backend: Optional[str] = None,
        similarity_threshold: Optional[float] = None,
        frame_sample_rate: Optional[int] = None,
    ):
        configured_backend = str(
            backend or getattr(settings, "AI_ML_IDENTITY_EMBEDDING_BACKEND", "auto")
        ).strip()
        self.requested_backend = configured_backend.lower()
        self.backend = self._resolve_backend(self.requested_backend)
        self.similarity_threshold = float(
            similarity_threshold
            if similarity_threshold is not None
            else getattr(settings, "AI_ML_IDENTITY_MATCH_THRESHOLD", 0.72)
        )
        self.frame_sample_rate = int(
            frame_sample_rate
            if frame_sample_rate is not None
            else getattr(settings, "AI_ML_IDENTITY_VIDEO_SAMPLE_RATE", 8)
        )

        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.face_cascade = cv2.CascadeClassifier(cascade_path)

        self.device = "cpu"
        self.mtcnn = None
        self.facenet_model = None

        if self.backend == "facenet":
            self._load_facenet_backend()

    @staticmethod
    def _facenet_available() -> bool:
        return all(
            dep is not None for dep in (torch, MTCNN, InceptionResnetV1)
        )

    @staticmethod
    def _deepface_available() -> bool:
        return DeepFace is not None

    def _resolve_backend(self, requested_backend: str) -> str:
        if requested_backend in {"", "auto"}:
            if self._facenet_available():
                return "facenet"
            if self._deepface_available():
                return "deepface"
            return "unavailable"

        if requested_backend == "facenet":
            if self._facenet_available():
                return "facenet"
            logger.warning(
                "Identity backend requested as facenet but facenet dependencies are missing."
            )
            if self._deepface_available():
                return "deepface"
            return "unavailable"

        if requested_backend == "deepface":
            if self._deepface_available():
                return "deepface"
            logger.warning(
                "Identity backend requested as deepface but deepface is not installed."
            )
            if self._facenet_available():
                return "facenet"
            return "unavailable"

        logger.warning(
            "Unknown identity backend '%s'; falling back to auto resolution.",
            requested_backend,
        )
        return self._resolve_backend("auto")

    def _load_facenet_backend(self) -> None:
        if not self._facenet_available():
            return
        if self.mtcnn is not None and self.facenet_model is not None:
            return

        self.device = "cuda:0" if torch is not None and torch.cuda.is_available() else "cpu"
        model_name = str(
            getattr(settings, "AI_ML_IDENTITY_FACENET_WEIGHTS", "vggface2")
        ).strip()

        self.mtcnn = MTCNN(
            image_size=160,
            margin=14,
            keep_all=False,
            post_process=True,
            device=self.device,
        )
        self.facenet_model = InceptionResnetV1(
            pretrained=model_name
        ).eval().to(self.device)

    @property
    def available(self) -> bool:
        return self.backend in {"facenet", "deepface"}

    def _read_document_image(self, document_path: str) -> np.ndarray:
        path = Path(document_path)
        if not path.exists():
            raise FileNotFoundError(f"Document not found: {path}")

        suffix = path.suffix.lower()
        if suffix == ".pdf":
            if convert_from_path is None:
                raise RuntimeError(
                    "pdf2image is required for PDF identity extraction but is not installed."
                )
            images = convert_from_path(
                str(path),
                first_page=1,
                last_page=1,
                **pdf2image_kwargs(),
            )
            if not images:
                raise ValueError(f"Could not rasterize first page of document: {path}")
            return cv2.cvtColor(np.array(images[0]), cv2.COLOR_RGB2BGR)

        image = cv2.imread(str(path))
        if image is None:
            raise ValueError(f"Could not read document image: {path}")
        return image

    def _detect_primary_face_bbox(
        self, image_bgr: np.ndarray
    ) -> Optional[Tuple[int, int, int, int]]:
        height, width = image_bgr.shape[:2]
        if height == 0 or width == 0:
            return None

        if self.backend == "facenet" and self.mtcnn is not None:
            rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
            boxes, probs = self.mtcnn.detect(rgb)
            if boxes is not None and len(boxes) > 0:
                best_idx = 0
                best_score = -1.0
                for idx, box in enumerate(boxes):
                    x1, y1, x2, y2 = box
                    area = max(0.0, (x2 - x1) * (y2 - y1))
                    prob = float(probs[idx]) if probs is not None else 1.0
                    score = area * max(prob, 0.0)
                    if score > best_score:
                        best_score = score
                        best_idx = idx

                x1, y1, x2, y2 = boxes[best_idx]
                x1 = int(max(0, np.floor(x1)))
                y1 = int(max(0, np.floor(y1)))
                x2 = int(min(width, np.ceil(x2)))
                y2 = int(min(height, np.ceil(y2)))
                if x2 > x1 and y2 > y1:
                    return x1, y1, x2 - x1, y2 - y1

        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(36, 36),
        )
        if len(faces) == 0:
            return None
        x, y, w, h = max(faces, key=lambda rect: rect[2] * rect[3])
        return int(x), int(y), int(w), int(h)

    def _crop_face(
        self, image_bgr: np.ndarray
    ) -> Tuple[Optional[np.ndarray], Optional[Tuple[int, int, int, int]]]:
        bbox = self._detect_primary_face_bbox(image_bgr)
        if bbox is None:
            return None, None

        x, y, w, h = bbox
        crop = image_bgr[y : y + h, x : x + w]
        if crop.size == 0:
            return None, None
        return crop, bbox

    def _extract_interview_face(
        self, interview_video_path: str
    ) -> Tuple[Optional[np.ndarray], Optional[Tuple[int, int, int, int]]]:
        path = Path(interview_video_path)
        if not path.exists():
            raise FileNotFoundError(f"Interview video not found: {path}")

        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise ValueError(f"Could not open interview video: {path}")

        best_face = None
        best_bbox = None
        best_score = -1.0
        frame_idx = 0

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                if frame_idx % max(1, self.frame_sample_rate) != 0:
                    frame_idx += 1
                    continue

                face, bbox = self._crop_face(frame)
                if face is None or bbox is None:
                    frame_idx += 1
                    continue

                x, y, w, h = bbox
                area = float(w * h)

                frame_h, frame_w = frame.shape[:2]
                face_cx = x + (w / 2.0)
                face_cy = y + (h / 2.0)
                frame_cx = frame_w / 2.0
                frame_cy = frame_h / 2.0
                dist = np.sqrt((face_cx - frame_cx) ** 2 + (face_cy - frame_cy) ** 2)
                max_dist = np.sqrt(frame_cx**2 + frame_cy**2) or 1.0
                center_score = max(0.0, 1.0 - (dist / max_dist))

                sharpness = cv2.Laplacian(
                    cv2.cvtColor(face, cv2.COLOR_BGR2GRAY),
                    cv2.CV_64F,
                ).var()
                sharpness_boost = min(float(sharpness) / 1000.0, 1.0)
                score = area * (0.7 + 0.3 * center_score) * (1.0 + 0.5 * sharpness_boost)

                if score > best_score:
                    best_score = score
                    best_face = face
                    best_bbox = bbox

                frame_idx += 1
        finally:
            cap.release()

        return best_face, best_bbox

    def _embedding_facenet(self, face_bgr: np.ndarray) -> np.ndarray:
        if torch is None:
            raise RuntimeError("torch is required for facenet backend.")
        if self.mtcnn is None or self.facenet_model is None:
            self._load_facenet_backend()

        rgb = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2RGB)
        aligned = self.mtcnn(rgb) if self.mtcnn is not None else None
        if aligned is None:
            resized = cv2.resize(rgb, (160, 160), interpolation=cv2.INTER_AREA)
            aligned = torch.from_numpy(resized).permute(2, 0, 1).float() / 255.0

        if aligned.ndim == 3:
            aligned = aligned.unsqueeze(0)

        with torch.no_grad():
            embedding = self.facenet_model(aligned.to(self.device))
        return embedding.detach().cpu().numpy().reshape(-1)

    @staticmethod
    def _embedding_deepface(face_bgr: np.ndarray) -> np.ndarray:
        if DeepFace is None:
            raise RuntimeError("deepface backend requested but deepface is unavailable.")

        rgb = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2RGB)
        result = DeepFace.represent(
            img_path=rgb,
            model_name="Facenet512",
            detector_backend="opencv",
            enforce_detection=False,
        )
        if not result:
            raise RuntimeError("DeepFace did not return an embedding.")

        if isinstance(result, list):
            payload = result[0]
        else:
            payload = result

        embedding = payload.get("embedding")
        if embedding is None:
            raise RuntimeError("DeepFace payload does not contain `embedding`.")

        return np.asarray(embedding, dtype=np.float32).reshape(-1)

    def _extract_embedding(self, face_bgr: np.ndarray) -> np.ndarray:
        if self.backend == "facenet":
            vector = self._embedding_facenet(face_bgr)
        elif self.backend == "deepface":
            vector = self._embedding_deepface(face_bgr)
        else:
            raise RuntimeError(
                "No identity embedding backend is available. "
                "Install facenet-pytorch (preferred) or deepface."
            )

        norm = np.linalg.norm(vector)
        if norm <= 1e-12:
            return vector
        return vector / norm

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        denom = float(np.linalg.norm(a) * np.linalg.norm(b))
        if denom <= 1e-12:
            return 0.0
        value = float(np.dot(a, b) / denom)
        return float(np.clip(value, -1.0, 1.0))

    def match_document_to_interview(
        self,
        document_path: str,
        interview_video_path: str,
    ) -> Dict:
        """
        Compare face from document against face captured from interview video.

        Returns a stable payload suitable for storing in JSONField.
        """
        started = time.time()
        response: Dict = {
            "enabled": True,
            "success": False,
            "backend_requested": self.requested_backend,
            "backend_used": self.backend,
            "threshold": round(float(self.similarity_threshold), 4),
            "document_face_detected": False,
            "interview_face_detected": False,
            "similarity_score": 0.0,
            "raw_cosine_similarity": 0.0,
            "is_match": False,
            "error": "",
            "processing_time_seconds": 0.0,
        }

        if not self.available:
            response["error"] = (
                "No embedding backend available. Install facenet-pytorch "
                "(preferred) or deepface."
            )
            response["processing_time_seconds"] = round(time.time() - started, 3)
            return response

        try:
            document_image = self._read_document_image(document_path)
            document_face, _ = self._crop_face(document_image)
            response["document_face_detected"] = document_face is not None
            if document_face is None:
                response["error"] = "No face detected in the provided document."
                return response

            interview_face, _ = self._extract_interview_face(interview_video_path)
            response["interview_face_detected"] = interview_face is not None
            if interview_face is None:
                response["error"] = "No face detected in interview video frames."
                return response

            document_embedding = self._extract_embedding(document_face)
            interview_embedding = self._extract_embedding(interview_face)

            raw_cosine = self._cosine_similarity(document_embedding, interview_embedding)
            normalized_similarity = max(0.0, min(1.0, (raw_cosine + 1.0) / 2.0))

            response["success"] = True
            response["raw_cosine_similarity"] = round(raw_cosine, 4)
            response["similarity_score"] = round(normalized_similarity, 4)
            response["is_match"] = normalized_similarity >= self.similarity_threshold
            return response
        except Exception as exc:
            logger.exception("Identity matching failed: %s", exc)
            response["error"] = str(exc)
            return response
        finally:
            response["processing_time_seconds"] = round(time.time() - started, 3)


def match_candidate_identity(document_path: str, interview_video_path: str) -> Dict:
    """Convenience helper for one-off identity matching."""
    matcher = IdentityMatcher()
    return matcher.match_document_to_interview(
        document_path=document_path,
        interview_video_path=interview_video_path,
    )

