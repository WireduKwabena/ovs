"""Traditional CV-based document authenticity checks."""

from __future__ import annotations

import logging
from typing import Dict

import cv2
import numpy as np
from PIL import Image
from PIL.ExifTags import TAGS

logger = logging.getLogger(__name__)


class CVAuthenticityDetector:
    """Computer-vision checks complementing deep-learning authenticity scoring."""

    def check_metadata(self, image_path: str) -> Dict:
        try:
            image = Image.open(image_path)
            exif_data = image._getexif()

            if not exif_data:
                return {
                    "has_metadata": False,
                    "suspicious": True,
                    "reason": "No EXIF metadata found",
                    "score": 60.0,
                }

            metadata = {TAGS.get(tag_id, tag_id): str(value) for tag_id, value in exif_data.items()}
            software = metadata.get("Software", "").lower()
            editing_software = {
                "photoshop",
                "gimp",
                "paint.net",
                "pixlr",
                "affinity",
                "illustrator",
                "corel",
                "inkscape",
            }
            edited = any(sw in software for sw in editing_software)

            suspicious_indicators = []
            if edited:
                suspicious_indicators.append(f"Editing software detected: {software}")

            if "DateTime" in metadata and "DateTimeOriginal" in metadata:
                if metadata["DateTime"] != metadata["DateTimeOriginal"]:
                    suspicious_indicators.append(
                        "Modification date differs from original capture date"
                    )

            score = 100.0 - (30.0 if edited else 0.0) - (20.0 if len(suspicious_indicators) > 1 else 0.0)

            return {
                "has_metadata": True,
                "suspicious": bool(suspicious_indicators),
                "software": software,
                "indicators": suspicious_indicators,
                "score": max(score, 0.0),
                "metadata_sample": {k: v for k, v in list(metadata.items())[:8]},
            }
        except Exception as exc:
            logger.error("Metadata check error: %s", exc)
            return {
                "has_metadata": False,
                "suspicious": True,
                "error": str(exc),
                "score": 70.0,
            }

    def detect_copy_move(self, image: np.ndarray) -> Dict:
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            using_orb = False
            try:
                detector = cv2.SIFT_create()
            except AttributeError:
                detector = cv2.ORB_create(nfeatures=1500)
                using_orb = True

            keypoints, descriptors = detector.detectAndCompute(gray, None)
            if descriptors is None or len(descriptors) < 2:
                return {
                    "copy_move_detected": False,
                    "similar_regions": 0,
                    "confidence": 0.0,
                    "score": 100.0,
                }

            if using_orb:
                matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
            else:
                matcher = cv2.BFMatcher()
            matches = matcher.knnMatch(descriptors, descriptors, k=2)

            good_matches = []
            for pair in matches:
                if len(pair) != 2:
                    continue
                m, n = pair
                if m.distance < 0.75 * n.distance and m.queryIdx != m.trainIdx:
                    pt1 = keypoints[m.queryIdx].pt
                    pt2 = keypoints[m.trainIdx].pt
                    if np.linalg.norm(np.array(pt1) - np.array(pt2)) > 50:
                        good_matches.append(m)

            detected = len(good_matches) > 15
            confidence = min((len(good_matches) / 30.0) * 100.0, 100.0)
            score = 100.0 - confidence if detected else 100.0

            return {
                "copy_move_detected": detected,
                "similar_regions": len(good_matches),
                "confidence": round(confidence, 2),
                "score": round(score, 2),
                "threshold": 15,
            }
        except Exception as exc:
            logger.error("Copy-move detection error: %s", exc)
            return {
                "copy_move_detected": False,
                "error": str(exc),
                "confidence": 0.0,
                "score": 100.0,
            }

    def check_compression_artifacts(self, image: np.ndarray) -> Dict:
        try:
            ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
            y_channel = ycrcb[:, :, 0]

            blockiness_score = self._calculate_blockiness(y_channel, block_size=8)
            dct = cv2.dct(np.float32(y_channel))
            coef_std = float(np.std(dct))
            coef_mean = float(np.mean(np.abs(dct)))

            suspicious = blockiness_score > 15
            score = max(100.0 - (blockiness_score * 3.0), 0.0)

            return {
                "coef_std": round(coef_std, 4),
                "coef_mean": round(coef_mean, 4),
                "blockiness": round(float(blockiness_score), 4),
                "suspicious": suspicious,
                "score": round(score, 2),
                "interpretation": (
                    "High compression artifacts detected"
                    if suspicious
                    else "Compression artifacts within expected range"
                ),
            }
        except Exception as exc:
            logger.error("Compression check error: %s", exc)
            return {
                "suspicious": False,
                "error": str(exc),
                "score": 100.0,
            }

    @staticmethod
    def _calculate_blockiness(image: np.ndarray, block_size: int = 8) -> float:
        h, w = image.shape
        block_diff = 0.0
        count = 0

        for i in range(0, h - block_size, block_size):
            for j in range(w):
                if i + block_size < h:
                    diff = abs(int(image[i + block_size - 1, j]) - int(image[i + block_size, j]))
                    block_diff += diff
                    count += 1

        for i in range(h):
            for j in range(0, w - block_size, block_size):
                if j + block_size < w:
                    diff = abs(int(image[i, j + block_size - 1]) - int(image[i, j + block_size]))
                    block_diff += diff
                    count += 1

        return block_diff / count if count > 0 else 0.0
