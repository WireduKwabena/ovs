from __future__ import annotations

from pathlib import Path
from typing import Dict

import cv2
import numpy as np


class DocumentFeatureExtractor:
    """Shared HOG + histogram feature extractor for document images."""

    def __init__(self, image_size: int = 128, hist_bins: int = 32):
        if image_size <= 0:
            raise ValueError("image_size must be > 0")
        if hist_bins <= 0:
            raise ValueError("hist_bins must be > 0")

        self.image_size = int(image_size)
        self.hist_bins = int(hist_bins)
        self.hog_descriptor = cv2.HOGDescriptor(
            _winSize=(self.image_size, self.image_size),
            _blockSize=(32, 32),
            _blockStride=(16, 16),
            _cellSize=(16, 16),
            _nbins=9,
        )

    @classmethod
    def from_config(cls, config: Dict[str, object] | None) -> "DocumentFeatureExtractor":
        if not isinstance(config, dict):
            return cls()
        image_size = int(config.get("image_size", 128))
        hist_bins = int(config.get("hist_bins", 32))
        return cls(image_size=image_size, hist_bins=hist_bins)

    def extract_from_path(self, image_path: Path) -> np.ndarray | None:
        image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            return None
        return self.extract_from_image(image)

    def extract_from_image(self, image: np.ndarray) -> np.ndarray | None:
        if image is None:
            return None

        if image.ndim == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        resized = cv2.resize(gray, (self.image_size, self.image_size), interpolation=cv2.INTER_AREA)
        hog = self.hog_descriptor.compute(resized)
        if hog is None:
            return None
        hog_vec = hog.flatten().astype(np.float32)

        hist = cv2.calcHist([resized], [0], None, [self.hist_bins], [0, 256]).flatten().astype(np.float32)
        hist_sum = float(hist.sum())
        if hist_sum > 0:
            hist = hist / hist_sum

        return np.concatenate([hog_vec, hist], axis=0).astype(np.float32)

    def config(self) -> Dict[str, object]:
        return {
            "type": "hog_histogram",
            "image_size": self.image_size,
            "hist_bins": self.hist_bins,
            "hog": {
                "win_size": [self.image_size, self.image_size],
                "block_size": [32, 32],
                "block_stride": [16, 16],
                "cell_size": [16, 16],
                "nbins": 9,
            },
        }
