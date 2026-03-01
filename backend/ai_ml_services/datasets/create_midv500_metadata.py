"""Build normalized metadata for MIDV-500 image frames and templates."""

from __future__ import annotations

import argparse
import json
import logging
import random
import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import pandas as pd

from ai_ml_services.datasets.metadata_utils import normalize_extensions

logger = logging.getLogger(__name__)

DEFAULT_EXTENSIONS = {".tif", ".tiff", ".png", ".jpg", ".jpeg", ".bmp"}


def normalize_midv_label(raw_label: str) -> str:
    """
    Normalize MIDV class folder names.

    Examples:
      - 01_alb_id -> alb_id
      - 47_usa_bordercrossing -> usa_bordercrossing
    """

    label = raw_label.lower().strip()
    label = re.sub(r"^\d+_", "", label)
    label = label.replace("-", "_")
    label = re.sub(r"_+", "_", label).strip("_")
    return label


def infer_midv_doc_family(label: str) -> str:
    normalized = str(label).lower().strip()
    if "drvlic" in normalized:
        return "driver_license"
    if "passport" in normalized:
        return "passport"
    if "ssn" in normalized:
        return "social_security_card"
    if "bordercrossing" in normalized:
        return "border_crossing_card"
    if "_id" in normalized or normalized.endswith("id") or "homereturn" in normalized:
        return "national_id"
    return "other"


def _parse_frame_index(frame_stem: str) -> Optional[int]:
    match = re.search(r"_(\d+)$", frame_stem)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _read_quad(annotation_path: Path) -> Optional[str]:
    try:
        payload = json.loads(annotation_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    quad = payload.get("quad") if isinstance(payload, dict) else None
    if not quad:
        return None
    try:
        return json.dumps(quad, separators=(",", ":"))
    except Exception:
        return None


def _assign_group_stratified_splits(
    df: pd.DataFrame,
    val_ratio: float,
    test_ratio: float,
    random_seed: int,
) -> pd.DataFrame:
    result = df.copy()
    result["split"] = "train"
    rng = random.Random(random_seed)

    for label in sorted(result["label"].unique()):
        label_mask = result["label"] == label
        groups = sorted(result.loc[label_mask, "group_id"].dropna().unique().tolist())
        if len(groups) < 2:
            continue

        rng.shuffle(groups)
        val_count = int(round(len(groups) * val_ratio))
        test_count = int(round(len(groups) * test_ratio))

        while val_count + test_count >= len(groups):
            if test_count > 0:
                test_count -= 1
            elif val_count > 0:
                val_count -= 1
            else:
                break

        val_groups = set(groups[:val_count])
        test_groups = set(groups[val_count : val_count + test_count])

        if val_groups:
            result.loc[label_mask & result["group_id"].isin(val_groups), "split"] = "val"
        if test_groups:
            result.loc[label_mask & result["group_id"].isin(test_groups), "split"] = "test"

    return result


def build_midv500_metadata(
    source_dir: Path,
    output_dir: Path,
    val_ratio: float = 0.1,
    test_ratio: float = 0.1,
    random_seed: int = 42,
    min_samples_per_label: int = 1,
    extensions: Sequence[str] = tuple(sorted(DEFAULT_EXTENSIONS)),
    include_templates: bool = True,
    include_frames: bool = True,
    max_frames_per_sequence: int = 0,
    parse_quads: bool = True,
) -> pd.DataFrame:
    if val_ratio < 0 or test_ratio < 0:
        raise ValueError("val_ratio and test_ratio must be >= 0.")
    if val_ratio + test_ratio >= 1:
        raise ValueError("val_ratio + test_ratio must be < 1.")
    if min_samples_per_label < 1:
        raise ValueError("min_samples_per_label must be >= 1.")
    if max_frames_per_sequence < 0:
        raise ValueError("max_frames_per_sequence must be >= 0.")
    if not include_templates and not include_frames:
        raise ValueError("At least one of include_templates/include_frames must be True.")

    allowed = normalize_extensions(extensions)
    rng = random.Random(random_seed)
    rows: List[Dict[str, object]] = []

    for class_dir in sorted(path for path in source_dir.iterdir() if path.is_dir()):
        label_raw = class_dir.name
        label = normalize_midv_label(label_raw)

        images_dir = class_dir / "images"
        gt_dir = class_dir / "ground_truth"
        if not images_dir.exists():
            logger.warning("Skipping %s (missing images directory)", class_dir)
            continue

        if include_templates:
            for template_path in sorted(images_dir.glob(f"{class_dir.name}.*")):
                if template_path.suffix.lower() not in allowed:
                    continue
                annotation_path = gt_dir / f"{class_dir.name}.json"
                rows.append(
                    {
                        "filename": template_path.name,
                        "filepath": str(template_path.resolve()),
                        "label_raw": label_raw,
                        "label": label,
                        "doc_family": infer_midv_doc_family(label),
                        "source_type": "template",
                        "sequence_id": "",
                        "frame_index": None,
                        "annotation_path": str(annotation_path.resolve()) if annotation_path.exists() else "",
                        "has_annotation": annotation_path.exists(),
                        "has_quad": False,
                        "quad_points": "",
                        "group_id": f"{label_raw}:template",
                    }
                )

        if include_frames:
            sequence_dirs = sorted(path for path in images_dir.iterdir() if path.is_dir())
            for sequence_dir in sequence_dirs:
                sequence_id = sequence_dir.name
                frame_paths = sorted(
                    p for p in sequence_dir.rglob("*") if p.is_file() and p.suffix.lower() in allowed
                )
                if max_frames_per_sequence > 0 and len(frame_paths) > max_frames_per_sequence:
                    frame_paths = sorted(rng.sample(frame_paths, max_frames_per_sequence))

                for frame_path in frame_paths:
                    annotation_path = gt_dir / sequence_id / f"{frame_path.stem}.json"
                    has_annotation = annotation_path.exists()
                    quad_points = _read_quad(annotation_path) if parse_quads and has_annotation else None
                    rows.append(
                        {
                            "filename": frame_path.name,
                            "filepath": str(frame_path.resolve()),
                            "label_raw": label_raw,
                            "label": label,
                            "doc_family": infer_midv_doc_family(label),
                            "source_type": "frame",
                            "sequence_id": sequence_id,
                            "frame_index": _parse_frame_index(frame_path.stem),
                            "annotation_path": str(annotation_path.resolve()) if has_annotation else "",
                            "has_annotation": has_annotation,
                            "has_quad": bool(quad_points),
                            "quad_points": quad_points or "",
                            "group_id": f"{label_raw}:{sequence_id}",
                        }
                    )

    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = output_dir / "metadata.csv"
    labels_path = output_dir / "labels.csv"
    aliases_path = output_dir / "raw_to_normalized_labels.csv"

    df = pd.DataFrame(rows)
    if df.empty:
        pd.DataFrame(
            columns=[
                "filename",
                "filepath",
                "label_raw",
                "label",
                "doc_family",
                "label_id",
                "source_type",
                "sequence_id",
                "frame_index",
                "annotation_path",
                "has_annotation",
                "has_quad",
                "quad_points",
                "group_id",
                "split",
            ]
        ).to_csv(metadata_path, index=False)
        pd.DataFrame(columns=["label_id", "label"]).to_csv(labels_path, index=False)
        pd.DataFrame(columns=["label_raw", "label"]).to_csv(aliases_path, index=False)
        logger.warning("No MIDV-500 files found. Wrote empty metadata to %s", metadata_path)
        return df

    if min_samples_per_label > 1:
        counts = df["label"].value_counts()
        keep = set(counts[counts >= min_samples_per_label].index.tolist())
        removed = len(df) - int(df["label"].isin(keep).sum())
        df = df[df["label"].isin(keep)].copy()
        if removed > 0:
            logger.info("Removed %d samples from labels below min_samples_per_label.", removed)

    if df.empty:
        pd.DataFrame(
            columns=[
                "filename",
                "filepath",
                "label_raw",
                "label",
                "doc_family",
                "label_id",
                "source_type",
                "sequence_id",
                "frame_index",
                "annotation_path",
                "has_annotation",
                "has_quad",
                "quad_points",
                "group_id",
                "split",
            ]
        ).to_csv(metadata_path, index=False)
        pd.DataFrame(columns=["label_id", "label"]).to_csv(labels_path, index=False)
        pd.DataFrame(columns=["label_raw", "label"]).to_csv(aliases_path, index=False)
        logger.warning("No MIDV-500 files left after filtering. Wrote empty metadata to %s", metadata_path)
        return df

    labels = sorted(df["label"].unique().tolist())
    label_to_id = {label: idx for idx, label in enumerate(labels)}
    df["label_id"] = df["label"].map(label_to_id)
    df = _assign_group_stratified_splits(
        df,
        val_ratio=val_ratio,
        test_ratio=test_ratio,
        random_seed=random_seed,
    )
    df.to_csv(metadata_path, index=False)

    pd.DataFrame(
        [{"label_id": idx, "label": label} for label, idx in label_to_id.items()]
    ).sort_values("label_id").to_csv(labels_path, index=False)

    (
        df[["label_raw", "label"]]
        .drop_duplicates()
        .sort_values(["label", "label_raw"])
        .to_csv(aliases_path, index=False)
    )

    logger.info(
        "MIDV-500 metadata written: %s (total=%d train=%d val=%d test=%d labels=%d)",
        metadata_path,
        len(df),
        int((df["split"] == "train").sum()),
        int((df["split"] == "val").sum()),
        int((df["split"] == "test").sum()),
        len(labels),
    )
    return df


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build normalized metadata for MIDV-500."
    )
    parser.add_argument(
        "--source_dir",
        type=str,
        default="ai_ml_services/datasets/raw_dataset/midv500",
        help="Root directory containing MIDV-500 class folders.",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="ai_ml_services/datasets/processed/midv500",
        help="Directory where metadata files are written.",
    )
    parser.add_argument(
        "--val_ratio",
        type=float,
        default=0.1,
        help="Validation split ratio per class (grouped by sequence_id).",
    )
    parser.add_argument(
        "--test_ratio",
        type=float,
        default=0.1,
        help="Test split ratio per class (grouped by sequence_id).",
    )
    parser.add_argument(
        "--min_samples_per_label",
        type=int,
        default=1,
        help="Drop labels with fewer samples than this threshold.",
    )
    parser.add_argument(
        "--random_seed",
        type=int,
        default=42,
        help="Random seed used for split assignment and optional frame sampling.",
    )
    parser.add_argument(
        "--extensions",
        nargs="*",
        default=sorted(DEFAULT_EXTENSIONS),
        help="Allowed image extensions (example: .tif .jpg).",
    )
    parser.add_argument(
        "--include_templates",
        action="store_true",
        help="Include class template images (images/<class_name>.*).",
    )
    parser.add_argument(
        "--include_frames",
        action="store_true",
        help="Include per-sequence frame images (images/<sequence>/*).",
    )
    parser.add_argument(
        "--max_frames_per_sequence",
        type=int,
        default=0,
        help="Optional cap per sequence directory (0 = no cap).",
    )
    parser.add_argument(
        "--no_parse_quads",
        action="store_true",
        help="Do not parse quad points from frame-level annotation JSON files.",
    )
    args = parser.parse_args()

    include_templates = args.include_templates
    include_frames = args.include_frames
    if not include_templates and not include_frames:
        include_templates = True
        include_frames = True

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    build_midv500_metadata(
        source_dir=Path(args.source_dir),
        output_dir=Path(args.output_dir),
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        random_seed=args.random_seed,
        min_samples_per_label=args.min_samples_per_label,
        extensions=args.extensions,
        include_templates=include_templates,
        include_frames=include_frames,
        max_frames_per_sequence=args.max_frames_per_sequence,
        parse_quads=not args.no_parse_quads,
    )


if __name__ == "__main__":
    main()
