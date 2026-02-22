"""Build a training-ready authenticity dataset from raw image folders."""

from __future__ import annotations

import argparse
import logging
import random
import re
import shutil
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import cv2
import numpy as np
import pandas as pd
from tqdm import tqdm

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".tif",
    ".tiff",
    ".webp",
}

AUTHENTIC_HINTS = {
    "authentic",
    "auth",
    "real",
    "original",
    "orig",
    "org",
    "au",
    "clean",
    "genuine",
}

FORGED_HINTS = {
    "forged",
    "forgeries",
    "forge",
    "forg",
    "fake",
    "tampered",
    "tamper",
    "tp",
    "splice",
    "spliced",
    "sp",
    "copymove",
    "manipulated",
}

COVERAGE_FILENAME_PATTERN = re.compile(r"^(?P<pair_id>\d+)(?P<tampered>t?)$", re.IGNORECASE)


class DocumentDatasetCreator:
    """Create a normalized dataset with `authentic/` and `forged/` buckets."""

    def __init__(self, output_dir: str = "data/custom_documents"):
        self.output_dir = Path(output_dir)
        self.authentic_dir = self.output_dir / "authentic"
        self.forged_dir = self.output_dir / "forged"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.authentic_dir.mkdir(exist_ok=True)
        self.forged_dir.mkdir(exist_ok=True)
        logger.info("Dataset output directory: %s", self.output_dir)

    @staticmethod
    def _normalize_suffix(path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix == ".jpeg":
            return ".jpg"
        if suffix == ".tiff":
            return ".tif"
        return suffix

    @staticmethod
    def _iter_images(source_path: Path) -> Iterable[Path]:
        if source_path.is_file() and source_path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS:
            yield source_path
            return
        if not source_path.is_dir():
            return
        for file_path in source_path.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS:
                yield file_path

    @staticmethod
    def _tokenize_path(path: Path) -> List[str]:
        tokens: List[str] = []
        for part in path.parts:
            piece = part.lower()
            tokens.extend(token for token in re.split(r"[^a-z0-9]+", piece) if token)
        return tokens

    @classmethod
    def infer_label_from_path(cls, image_path: Path) -> Optional[str]:
        filename = image_path.name.lower()
        if filename.startswith("cf-"):
            return "forged"
        if filename.startswith("c-"):
            return "authentic"
        if filename.startswith("forgeries_"):
            return "forged"
        if filename.startswith("original_"):
            return "authentic"

        tokens = set(cls._tokenize_path(image_path))
        if tokens.intersection(FORGED_HINTS):
            return "forged"
        if tokens.intersection(AUTHENTIC_HINTS):
            return "authentic"
        return None

    def _copy_image(self, image_path: Path, label: str, index: int) -> Optional[Path]:
        target_dir = self.authentic_dir if label == "authentic" else self.forged_dir
        suffix = self._normalize_suffix(image_path)
        dest = target_dir / f"{label}_{index:07d}{suffix}"
        try:
            shutil.copy2(image_path, dest)
            return dest
        except Exception as exc:
            logger.warning("Failed to copy %s -> %s: %s", image_path, dest, exc)
            return None

    def collect_documents(
        self,
        source_dirs: List[str],
        label: str,
        max_images_per_source: int = 0,
    ) -> int:
        if label not in {"authentic", "forged"}:
            raise ValueError("label must be 'authentic' or 'forged'")
        if not source_dirs:
            return 0

        target_dir = self.authentic_dir if label == "authentic" else self.forged_dir
        next_index = len(list(self._iter_images(target_dir)))
        copied = 0
        logger.info("Collecting %s samples from %s", label, source_dirs)
        for source in source_dirs:
            source_path = Path(source)
            images = list(self._iter_images(source_path))
            if max_images_per_source > 0 and len(images) > max_images_per_source:
                images = random.sample(images, max_images_per_source)
            for image_path in tqdm(images, desc=f"Copy {label} from {source_path.name}"):
                if self._copy_image(image_path, label, next_index) is not None:
                    copied += 1
                    next_index += 1
        logger.info("Collected %d %s samples.", copied, label)
        return copied

    def collect_auto_labeled_documents(
        self,
        source_dirs: List[str],
        max_images_per_source: int = 0,
    ) -> Dict[str, int]:
        counts = {"authentic": 0, "forged": 0, "skipped": 0}
        next_indices = {
            "authentic": len(list(self._iter_images(self.authentic_dir))),
            "forged": len(list(self._iter_images(self.forged_dir))),
        }
        if not source_dirs:
            return counts

        logger.info("Collecting auto-labeled samples from %s", source_dirs)
        for source in source_dirs:
            source_path = Path(source)
            images = list(self._iter_images(source_path))
            if max_images_per_source > 0 and len(images) > max_images_per_source:
                images = random.sample(images, max_images_per_source)

            for image_path in tqdm(images, desc=f"Auto-label {source_path.name}"):
                label = self.infer_label_from_path(image_path)
                if label is None:
                    counts["skipped"] += 1
                    continue
                idx = next_indices[label]
                if self._copy_image(image_path, label, idx) is not None:
                    counts[label] += 1
                    next_indices[label] += 1
        logger.info(
            "Auto-labeled samples -> authentic=%d forged=%d skipped=%d",
            counts["authentic"],
            counts["forged"],
            counts["skipped"],
        )
        return counts

    def collect_coverage_documents(
        self,
        source_dirs: List[str],
        max_pairs_per_source: int = 0,
    ) -> Dict[str, int]:
        """
        Ingest COVERAGE dataset pairs.

        Expected naming inside each source root:
        - image/{id}.tif   -> authentic
        - image/{id}t.tif  -> forged
        """

        counts = {"authentic": 0, "forged": 0, "skipped": 0}
        next_indices = {
            "authentic": len(list(self._iter_images(self.authentic_dir))),
            "forged": len(list(self._iter_images(self.forged_dir))),
        }
        if not source_dirs:
            return counts

        for source in source_dirs:
            source_root = Path(source)
            image_dir = source_root / "image" if (source_root / "image").is_dir() else source_root
            if not image_dir.exists():
                logger.warning("COVERAGE source path not found: %s", source_root)
                counts["skipped"] += 1
                continue

            pair_map: Dict[str, Dict[str, Path]] = {}
            invalid_names = 0
            for image_path in self._iter_images(image_dir):
                match = COVERAGE_FILENAME_PATTERN.fullmatch(image_path.stem.lower())
                if not match:
                    invalid_names += 1
                    continue
                pair_id = match.group("pair_id")
                label = "forged" if match.group("tampered") == "t" else "authentic"
                pair_map.setdefault(pair_id, {})[label] = image_path

            pair_ids = sorted(pair_map.keys(), key=lambda value: int(value))
            if max_pairs_per_source > 0 and len(pair_ids) > max_pairs_per_source:
                pair_ids = random.sample(pair_ids, max_pairs_per_source)
                pair_ids.sort(key=lambda value: int(value))

            for pair_id in pair_ids:
                pair = pair_map[pair_id]
                for label in ("authentic", "forged"):
                    image_path = pair.get(label)
                    if image_path is None:
                        counts["skipped"] += 1
                        continue
                    idx = next_indices[label]
                    if self._copy_image(image_path, label, idx) is not None:
                        counts[label] += 1
                        next_indices[label] += 1
                    else:
                        counts["skipped"] += 1

            logger.info(
                "Processed COVERAGE source %s -> authentic=%d forged=%d skipped=%d invalid_names=%d",
                source_root,
                counts["authentic"],
                counts["forged"],
                counts["skipped"],
                invalid_names,
            )
        return counts

    def collect_authentic_documents(
        self,
        source_dirs: List[str],
        max_images_per_source: int = 0,
    ) -> int:
        return self.collect_documents(
            source_dirs=source_dirs,
            label="authentic",
            max_images_per_source=max_images_per_source,
        )

    def collect_forged_documents(
        self,
        source_dirs: List[str],
        max_images_per_source: int = 0,
    ) -> int:
        return self.collect_documents(
            source_dirs=source_dirs,
            label="forged",
            max_images_per_source=max_images_per_source,
        )

    def generate_forged_documents(self, num_forgeries: int = 1000) -> int:
        """Generate synthetic forged documents from authentic images."""
        authentic_images = list(self._iter_images(self.authentic_dir))
        if not authentic_images:
            logger.warning("No authentic images found. Skipping synthetic forgery generation.")
            return 0
        if num_forgeries <= 0:
            return 0

        generated = 0
        next_index = len(list(self._iter_images(self.forged_dir)))
        logger.info("Generating %d synthetic forged samples...", num_forgeries)
        while generated < num_forgeries:
            try:
                source_path = random.choice(authentic_images)
                img = cv2.imread(str(source_path))
                if img is None:
                    continue
                method = random.choice(
                    [
                        self._create_splicing_forgery,
                        self._create_copy_move_forgery,
                        self._create_content_replacement,
                        self._create_region_removal,
                    ]
                )
                forged = method(img.copy())
                out_path = self.forged_dir / f"forged_{next_index:07d}{self._normalize_suffix(source_path)}"
                cv2.imwrite(str(out_path), forged)
                generated += 1
                next_index += 1
            except Exception as exc:
                logger.warning("Synthetic forgery generation failed: %s", exc)
        logger.info("Generated %d synthetic forged documents.", generated)
        return generated

    def _create_splicing_forgery(self, img: np.ndarray) -> np.ndarray:
        h, w = img.shape[:2]
        all_images = list(self._iter_images(self.authentic_dir))
        if len(all_images) < 2:
            return self._create_copy_move_forgery(img)

        other_img = None
        for _ in range(10):
            other_path = random.choice(all_images)
            candidate = cv2.imread(str(other_path))
            if candidate is not None:
                other_img = cv2.resize(candidate, (w, h))
                break
        if other_img is None:
            return img

        min_dim = min(h, w)
        if min_dim < 50:
            return img

        region_size_w = random.randint(min_dim // 5, min_dim // 2)
        region_size_h = random.randint(min_dim // 5, min_dim // 2)
        x1 = random.randint(0, w - region_size_w)
        y1 = random.randint(0, h - region_size_h)
        x2 = x1 + region_size_w
        y2 = y1 + region_size_h

        mask = np.zeros((h, w), dtype=np.uint8)
        mask[y1:y2, x1:x2] = 255
        mask_3ch = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR) / 255.0
        return (img * (1 - mask_3ch) + other_img * mask_3ch).astype(np.uint8)

    @staticmethod
    def _create_copy_move_forgery(img: np.ndarray) -> np.ndarray:
        h, w = img.shape[:2]
        min_dim = min(h, w)
        if min_dim < 50:
            return img

        region_h = random.randint(min_dim // 8, min_dim // 4)
        region_w = random.randint(min_dim // 8, min_dim // 4)
        if w - region_w <= 0 or h - region_h <= 0:
            return img

        src_x = random.randint(0, w - region_w)
        src_y = random.randint(0, h - region_h)
        dst_x = random.randint(0, w - region_w)
        dst_y = random.randint(0, h - region_h)

        forged = img.copy()
        region = img[src_y : src_y + region_h, src_x : src_x + region_w]
        forged[dst_y : dst_y + region_h, dst_x : dst_x + region_w] = region
        return forged

    @staticmethod
    def _create_content_replacement(img: np.ndarray) -> np.ndarray:
        forged = img.copy()
        h, w = img.shape[:2]
        font = cv2.FONT_HERSHEY_SIMPLEX
        for _ in range(random.randint(1, 3)):
            text = "".join(str(random.randint(0, 9)) for _ in range(random.randint(4, 8)))
            (text_w, text_h), _ = cv2.getTextSize(text, font, 0.7, 2)
            if w - text_w - 50 <= 0 or h - text_h - 50 <= 0:
                continue
            x = random.randint(20, w - text_w - 30)
            y = random.randint(text_h + 20, h - 20)
            cv2.rectangle(forged, (x - 5, y - text_h - 5), (x + text_w + 5, y + 5), (255, 255, 255), -1)
            cv2.putText(forged, text, (x, y), font, 0.7, (0, 0, 0), 2)
        return forged

    @staticmethod
    def _create_region_removal(img: np.ndarray) -> np.ndarray:
        forged = img.copy()
        h, w = img.shape[:2]
        for _ in range(random.randint(1, 2)):
            min_rect_w, min_rect_h = 30, 20
            if w < min_rect_w + 20 or h < min_rect_h + 20:
                continue
            x1 = random.randint(0, w - min_rect_w - 10)
            y1 = random.randint(0, h - min_rect_h - 10)
            x2 = x1 + random.randint(min_rect_w, min(w - x1, 150))
            y2 = y1 + random.randint(min_rect_h, min(h - y1, 80))
            cv2.rectangle(forged, (x1, y1), (x2, y2), (255, 255, 255), -1)
        return forged

    def create_metadata_file(self, random_seed: int = 42, val_ratio: float = 0.2) -> pd.DataFrame:
        rows: List[Dict[str, str]] = []
        for label, folder in (("authentic", self.authentic_dir), ("forged", self.forged_dir)):
            for img_path in self._iter_images(folder):
                rows.append(
                    {
                        "filename": img_path.name,
                        "label": label,
                        "category": label,
                        "filepath": str(img_path.resolve()),
                    }
                )

        df = pd.DataFrame(rows)
        if df.empty:
            metadata_path = self.output_dir / "metadata.csv"
            df.to_csv(metadata_path, index=False)
            logger.warning("No samples found; wrote empty metadata at %s", metadata_path)
            return df

        df["split"] = "train"
        rng = np.random.default_rng(random_seed)
        for label in sorted(df["label"].unique()):
            idx = df.index[df["label"] == label].to_numpy()
            if len(idx) < 2:
                continue
            desired = max(1, int(round(len(idx) * val_ratio)))
            val_count = min(desired, len(idx) - 1)
            val_idx = rng.choice(idx, size=val_count, replace=False)
            df.loc[val_idx, "split"] = "val"

        metadata_path = self.output_dir / "metadata.csv"
        df.to_csv(metadata_path, index=False)
        logger.info(
            "Metadata created at %s (total=%d train=%d val=%d)",
            metadata_path,
            len(df),
            int((df["split"] == "train").sum()),
            int((df["split"] == "val").sum()),
        )
        return df


def main():
    parser = argparse.ArgumentParser(
        description="Build authenticity dataset from raw folders and optional synthetic forgeries."
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="data/custom_documents",
        help="Directory to save normalized dataset and metadata.csv.",
    )
    parser.add_argument(
        "--authentic_sources",
        nargs="*",
        default=[],
        help="Directories/files containing authentic images.",
    )
    parser.add_argument(
        "--forged_sources",
        nargs="*",
        default=[],
        help="Directories/files containing already forged/tampered images.",
    )
    parser.add_argument(
        "--auto_labeled_sources",
        nargs="*",
        default=[],
        help="Sources that include mixed labels in path names (e.g. Au/Tp, real/fake).",
    )
    parser.add_argument(
        "--coverage_sources",
        nargs="*",
        default=[],
        help=(
            "COVERAGE dataset roots. Each root may contain image/{id}.tif (authentic) "
            "and image/{id}t.tif (forged)."
        ),
    )
    parser.add_argument(
        "--num_forgeries",
        type=int,
        default=0,
        help="Number of synthetic forged samples to generate from authentic pool.",
    )
    parser.add_argument(
        "--max_images_per_source",
        type=int,
        default=0,
        help="Optional cap per source directory (0 = no cap).",
    )
    parser.add_argument(
        "--random_seed",
        type=int,
        default=42,
        help="Random seed for reproducibility.",
    )
    parser.add_argument(
        "--val_ratio",
        type=float,
        default=0.2,
        help="Validation split ratio per class.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    random.seed(args.random_seed)
    np.random.seed(args.random_seed)

    creator = DocumentDatasetCreator(output_dir=args.output_dir)
    authentic_count = creator.collect_authentic_documents(
        source_dirs=args.authentic_sources,
        max_images_per_source=args.max_images_per_source,
    )
    forged_count = creator.collect_forged_documents(
        source_dirs=args.forged_sources,
        max_images_per_source=args.max_images_per_source,
    )
    auto_counts = creator.collect_auto_labeled_documents(
        source_dirs=args.auto_labeled_sources,
        max_images_per_source=args.max_images_per_source,
    )
    authentic_count += auto_counts["authentic"]
    forged_count += auto_counts["forged"]
    coverage_counts = creator.collect_coverage_documents(
        source_dirs=args.coverage_sources,
        max_pairs_per_source=args.max_images_per_source,
    )
    authentic_count += coverage_counts["authentic"]
    forged_count += coverage_counts["forged"]

    if authentic_count == 0:
        logger.error("No authentic samples collected. Cannot build dataset.")
        raise SystemExit(1)

    if args.num_forgeries > 0:
        forged_count += creator.generate_forged_documents(num_forgeries=args.num_forgeries)

    if forged_count == 0:
        logger.warning(
            "No forged samples present. Consider adding --forged_sources or --num_forgeries."
        )

    creator.create_metadata_file(random_seed=args.random_seed, val_ratio=args.val_ratio)


if __name__ == "__main__":
    main()
