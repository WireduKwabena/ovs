"""Synthetic forgery generation utilities for authenticity training."""

from __future__ import annotations

import argparse
import logging
import random
from pathlib import Path
from typing import Iterable, Sequence

import cv2
import numpy as np
from PIL import Image
from tqdm import tqdm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
SUPPORTED_FORGERY_TYPES = {"copy_move", "resampling", "jpeg"}


class ForgeryGenerator:
    """Generate synthetic forgeries from authentic documents."""

    def __init__(self, seed: int | None = None):
        self.seed = seed
        self.rng = random.Random(seed)

    def _choose_region_size(self, height: int, width: int, min_scale: float, max_scale: float) -> tuple[int, int]:
        min_h = max(1, int(height * min_scale))
        max_h = max(min_h, int(height * max_scale))
        min_w = max(1, int(width * min_scale))
        max_w = max(min_w, int(width * max_scale))
        return self.rng.randint(min_h, max_h), self.rng.randint(min_w, max_w)

    def copy_move_forgery(self, image: np.ndarray, num_regions: int = 1) -> np.ndarray:
        """Create copy-move forgery by duplicating regions."""
        h, w = image.shape[:2]
        if h < 8 or w < 8:
            return image.copy()
        forged = image.copy()

        for _ in range(max(1, int(num_regions))):
            region_h, region_w = self._choose_region_size(h, w, 0.1, 0.3)
            if region_h >= h or region_w >= w:
                continue

            src_x = self.rng.randint(0, max(0, w - region_w))
            src_y = self.rng.randint(0, max(0, h - region_h))
            dst_x = self.rng.randint(0, max(0, w - region_w))
            dst_y = self.rng.randint(0, max(0, h - region_h))

            attempts = 0
            while abs(dst_x - src_x) < region_w and abs(dst_y - src_y) < region_h:
                if attempts >= 8:
                    break
                dst_x = self.rng.randint(0, max(0, w - region_w))
                dst_y = self.rng.randint(0, max(0, h - region_h))
                attempts += 1

            region = image[src_y : src_y + region_h, src_x : src_x + region_w]
            forged[dst_y : dst_y + region_h, dst_x : dst_x + region_w] = region

        return forged

    def resampling_forgery(self, image: np.ndarray) -> np.ndarray:
        """Create resampling forgery by resizing regions."""
        h, w = image.shape[:2]
        if h < 8 or w < 8:
            return image.copy()
        forged = image.copy()

        region_h, region_w = self._choose_region_size(h, w, 0.2, 0.4)
        if region_h >= h or region_w >= w:
            return forged

        x = self.rng.randint(0, max(0, w - region_w))
        y = self.rng.randint(0, max(0, h - region_h))

        region = image[y : y + region_h, x : x + region_w]
        scale = self.rng.uniform(0.6, 0.9)
        resized = cv2.resize(region, (max(1, int(region_w * scale)), max(1, int(region_h * scale))))
        padded = cv2.resize(resized, (region_w, region_h))
        forged[y : y + region_h, x : x + region_w] = padded

        return forged

    def jpeg_compression_attack(self, image: np.ndarray, quality: int | None = None) -> np.ndarray:
        """Apply JPEG compression."""
        if quality is None:
            quality = self.rng.randint(60, 85)

        pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

        import io

        buffer = io.BytesIO()
        pil_image.save(buffer, format="JPEG", quality=int(quality))
        buffer.seek(0)
        compressed = Image.open(buffer)

        return cv2.cvtColor(np.array(compressed), cv2.COLOR_RGB2BGR)


def _iter_images(input_path: Path, recursive: bool) -> Iterable[Path]:
    iterator = input_path.rglob("*") if recursive else input_path.glob("*")
    for file_path in iterator:
        if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS:
            yield file_path


def generate_forgeries(
    input_dir: str,
    output_dir: str,
    num_per_image: int = 3,
    forgery_types: Sequence[str] | None = None,
    random_seed: int = 42,
    recursive: bool = False,
) -> int:
    """Generate synthetic forgeries and return number of files written."""
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    if not input_path.exists():
        raise FileNotFoundError(f"Input path not found: {input_path}")
    if num_per_image < 1:
        raise ValueError("num_per_image must be >= 1")

    output_path.mkdir(parents=True, exist_ok=True)

    selected_types = [item.strip().lower() for item in (forgery_types or ("copy_move", "resampling", "jpeg")) if item]
    unsupported = set(selected_types).difference(SUPPORTED_FORGERY_TYPES)
    if unsupported:
        raise ValueError(f"Unsupported forgery types: {sorted(unsupported)}")
    if not selected_types:
        raise ValueError("At least one forgery type must be selected.")

    generator = ForgeryGenerator(seed=random_seed)

    image_files = sorted(_iter_images(input_path, recursive=recursive))
    logger.info("Found %d authentic images in %s", len(image_files), input_path)

    generated = 0
    for img_file in tqdm(image_files, desc="Generating"):
        image = cv2.imread(str(img_file))
        if image is None:
            logger.warning("Skipping unreadable image: %s", img_file)
            continue

        for i in range(num_per_image):
            forgery_type = generator.rng.choice(selected_types)
            if forgery_type == "copy_move":
                forged = generator.copy_move_forgery(image)
            elif forgery_type == "resampling":
                forged = generator.resampling_forgery(image)
            else:
                forged = generator.jpeg_compression_attack(image)

            output_file = output_path / f"{img_file.stem}_forged_{i}.jpg"
            cv2.imwrite(str(output_file), forged)
            generated += 1

    logger.info("Generated %d forged samples in %s", generated, output_path)
    return generated


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic forged document variants.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--num_per_image", type=int, default=3)
    parser.add_argument(
        "--forgery_types",
        nargs="*",
        default=["copy_move", "resampling", "jpeg"],
        help="Subset of forgery types: copy_move resampling jpeg",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--recursive", action="store_true")

    args = parser.parse_args()
    generate_forgeries(
        input_dir=args.input,
        output_dir=args.output,
        num_per_image=args.num_per_image,
        forgery_types=args.forgery_types,
        random_seed=args.seed,
        recursive=args.recursive,
    )
