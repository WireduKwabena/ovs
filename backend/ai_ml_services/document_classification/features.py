from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class DocumentFeatureExtractor:
    """Shared document feature extractor (HOG/histogram or ResNet embeddings)."""

    SUPPORTED_BACKENDS = {"hog_histogram", "resnet18_embedding", "hybrid_hog_resnet"}

    def __init__(
        self,
        image_size: int = 128,
        hist_bins: int = 32,
        backend: str = "hog_histogram",
        resnet_pretrained: bool = True,
        resnet_device: str = "auto",
    ):
        if image_size <= 0:
            raise ValueError("image_size must be > 0")
        if hist_bins <= 0:
            raise ValueError("hist_bins must be > 0")

        normalized_backend = str(backend).strip().lower()
        if normalized_backend not in self.SUPPORTED_BACKENDS:
            raise ValueError(
                f"Unsupported backend `{backend}`. Supported: {sorted(self.SUPPORTED_BACKENDS)}"
            )

        self.image_size = int(image_size)
        self.hist_bins = int(hist_bins)
        self.backend = normalized_backend
        self.resnet_pretrained = bool(resnet_pretrained)
        self.resnet_device_mode = str(resnet_device).strip().lower() or "auto"

        self.hog_descriptor = None
        self._torch = None
        self._resnet_model = None
        self._resnet_device = None

        if self.backend == "hog_histogram" or self.backend == "hybrid_hog_resnet":
            self.hog_descriptor = cv2.HOGDescriptor(
                _winSize=(self.image_size, self.image_size),
                _blockSize=(32, 32),
                _blockStride=(16, 16),
                _cellSize=(16, 16),
                _nbins=9,
            )
        if self.backend == "resnet18_embedding" or self.backend == "hybrid_hog_resnet":
            self._init_resnet_backend()

    @classmethod
    def from_config(cls, config: Dict[str, object] | None) -> "DocumentFeatureExtractor":
        if not isinstance(config, dict):
            return cls()
        backend = str(config.get("type", "hog_histogram"))
        image_size = int(config.get("image_size", 128))
        hist_bins = int(config.get("hist_bins", 32))
        resnet_pretrained = bool(config.get("resnet_pretrained", True))
        resnet_device = str(config.get("resnet_device", "auto"))
        return cls(
            image_size=image_size,
            hist_bins=hist_bins,
            backend=backend,
            resnet_pretrained=resnet_pretrained,
            resnet_device=resnet_device,
        )

    def _init_resnet_backend(self) -> None:
        try:
            import torch
            from torchvision import models as tv_models
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "resnet18_embedding backend requires torch and torchvision."
            ) from exc

        device_mode = self.resnet_device_mode
        if device_mode not in {"auto", "cpu", "cuda"}:
            raise ValueError("resnet_device must be one of: auto, cpu, cuda")

        if device_mode == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        elif device_mode == "cuda":
            if not torch.cuda.is_available():
                raise RuntimeError("resnet_device=cuda requested but CUDA is unavailable.")
            device = "cuda"
        else:
            device = "cpu"

        if self.resnet_pretrained:
            try:
                weights = tv_models.ResNet18_Weights.DEFAULT
                model = tv_models.resnet18(weights=weights)
            except (AttributeError, TypeError):
                model = tv_models.resnet18(pretrained=True)
        else:
            try:
                model = tv_models.resnet18(weights=None)
            except TypeError:
                model = tv_models.resnet18(pretrained=False)

        model.fc = torch.nn.Identity()
        model.eval()
        model.to(device)

        self._torch = torch
        self._resnet_model = model
        self._resnet_device = device

        logger.info(
            "Initialized document feature backend resnet18_embedding (pretrained=%s, device=%s)",
            self.resnet_pretrained,
            self._resnet_device,
        )

    def extract_from_path(self, image_path: Path) -> np.ndarray | None:
        if self.backend == "resnet18_embedding" or self.backend == "hybrid_hog_resnet":
            image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        else:
            image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            return None
        return self.extract_from_image(image)

    def _extract_hog_features(self, image: np.ndarray) -> np.ndarray | None:
        if image.ndim == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        resized = cv2.resize(gray, (self.image_size, self.image_size), interpolation=cv2.INTER_AREA)
        hog = self.hog_descriptor.compute(resized) if self.hog_descriptor is not None else None
        if hog is None:
            return None
        hog_vec = hog.flatten().astype(np.float32)

        hist = cv2.calcHist([resized], [0], None, [self.hist_bins], [0, 256]).flatten().astype(np.float32)
        hist_sum = float(hist.sum())
        if hist_sum > 0:
            hist = hist / hist_sum

        return np.concatenate([hog_vec, hist], axis=0).astype(np.float32)

    def _extract_resnet_embedding(self, image: np.ndarray) -> np.ndarray | None:
        if self._torch is None or self._resnet_model is None or self._resnet_device is None:
            raise RuntimeError("ResNet feature backend is not initialized.")

        if image.ndim == 2:
            rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        elif image.shape[2] == 4:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGRA2RGB)
        else:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        resized = cv2.resize(rgb, (224, 224), interpolation=cv2.INTER_AREA)
        tensor = self._torch.from_numpy(resized.transpose(2, 0, 1)).to(self._torch.float32) / 255.0

        mean = self._torch.tensor([0.485, 0.456, 0.406], dtype=self._torch.float32).view(3, 1, 1)
        std = self._torch.tensor([0.229, 0.224, 0.225], dtype=self._torch.float32).view(3, 1, 1)
        tensor = (tensor - mean) / std
        tensor = tensor.unsqueeze(0).to(self._resnet_device)

        with self._torch.no_grad():
            features = self._resnet_model(tensor)

        if isinstance(features, (tuple, list)):
            features = features[0]

        return features.detach().cpu().numpy().reshape(-1).astype(np.float32)

    def extract_from_image(self, image: np.ndarray) -> np.ndarray | None:
        if image is None:
            return None

        if self.backend == "resnet18_embedding":
            return self._extract_resnet_embedding(image)
        return self._extract_hog_features(image)

    def config(self) -> Dict[str, object]:
        if self.backend == "resnet18_embedding":
            return {
                "type": "resnet18_embedding",
                "image_size": self.image_size,
                "hist_bins": self.hist_bins,
                "resnet_pretrained": self.resnet_pretrained,
                "resnet_device": self.resnet_device_mode,
                "embedding_dim": 512,
            }

        if self.backend == "hybrid_hog_resnet":
            return {
                "type": "hybrid_hog_resnet",
                "image_size": self.image_size,
                "hist_bins": self.hist_bins,
                "resnet_pretrained": self.resnet_pretrained,
                "resnet_device": self.resnet_device_mode,
                "embedding_dim": 512,
                "hog": {
                    "win_size": [self.image_size, self.image_size],
                    "block_size": [32, 32],
                    "block_stride": [16, 16],
                    "cell_size": [16, 16],
                    "nbins": 9,
                },
            }

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
