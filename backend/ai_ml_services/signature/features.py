"""Feature extraction utilities for signature authenticity modeling."""

from __future__ import annotations

from typing import Tuple

import cv2
import numpy as np

SIGNATURE_CANVAS_SIZE: Tuple[int, int] = (128, 256)  # height, width


def preprocess_signature(image: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Return normalized grayscale and binary signature maps."""
    if image is None:
        raise ValueError("image cannot be None")

    if len(image.shape) == 2:
        gray = image
    elif image.shape[2] == 4:
        gray = cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
    else:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    height, width = SIGNATURE_CANVAS_SIZE
    gray = cv2.resize(gray, (width, height), interpolation=cv2.INTER_AREA)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Keep white background / dark ink convention.
    if float(binary.mean()) < 127.0:
        binary = cv2.bitwise_not(binary)

    return gray, binary


def extract_signature_features(image: np.ndarray) -> np.ndarray:
    """Extract robust statistical features from a signature image."""
    gray, binary = preprocess_signature(image)
    ink = (binary < 128).astype(np.uint8)

    # Global structure.
    h_proj = ink.mean(axis=1).astype(np.float32)  # 128
    w_proj = ink.mean(axis=0).astype(np.float32)  # 256

    # Texture and stroke maps.
    low_res = cv2.resize(gray, (32, 16), interpolation=cv2.INTER_AREA).astype(np.float32)
    low_res = (low_res / 255.0).flatten()  # 512

    edges = cv2.Canny(gray, threshold1=60, threshold2=140)
    edge_density = np.array([float((edges > 0).mean())], dtype=np.float32)
    ink_density = np.array([float(ink.mean())], dtype=np.float32)

    # Shape moments (log-scaled for numeric stability).
    hu = cv2.HuMoments(cv2.moments(ink.astype(np.float32))).flatten().astype(np.float32)
    hu = np.sign(hu) * np.log1p(np.abs(hu))

    # Bounding box stats.
    points = np.column_stack(np.where(ink > 0))
    if points.size == 0:
        bbox_stats = np.array([0.0, 0.0, 0.0], dtype=np.float32)
    else:
        y_min, x_min = points.min(axis=0)
        y_max, x_max = points.max(axis=0)
        bbox_h = max(1, int(y_max - y_min + 1))
        bbox_w = max(1, int(x_max - x_min + 1))
        canvas_h, canvas_w = ink.shape
        bbox_area = float(bbox_h * bbox_w) / float(canvas_h * canvas_w)
        bbox_aspect = float(bbox_w) / float(bbox_h)
        bbox_stats = np.array(
            [
                float(bbox_h) / float(canvas_h),
                float(bbox_w) / float(canvas_w),
                bbox_area * bbox_aspect,
            ],
            dtype=np.float32,
        )

    feature_vector = np.concatenate(
        [low_res, h_proj, w_proj, edge_density, ink_density, hu, bbox_stats]
    )
    return feature_vector.astype(np.float32)
