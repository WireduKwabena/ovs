"""Build normalized metadata for the RVL-CDIP document classification dataset."""

from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import pandas as pd

from ai_ml_services.datasets.metadata_utils import assign_stratified_splits, normalize_extensions

logger = logging.getLogger(__name__)

DEFAULT_EXTENSIONS = {".tif", ".tiff", ".png", ".jpg", ".jpeg", ".bmp"}

# Keyed by compact token (lowercase, non-alphanumeric removed).
RVL_LABEL_ALIASES: Dict[str, str] = {
    "advertisement": "advertisement",
    "budget": "budget",
    "email": "email",
    "filefolder": "file_folder",
    "form": "form",
    "handwritten": "handwritten",
    "invoice": "invoice",
    "letter": "letter",
    "memo": "memo",
    "newsarticle": "news_article",
    "presentation": "presentation",
    "questionnaire": "questionnaire",
    "resume": "resume",
    "scientificpublication": "scientific_publication",
    "scientificreport": "scientific_report",
    "specification": "specification",
}

RVL_DOC_FAMILY_MAP: Dict[str, str] = {
    "advertisement": "media_marketing",
    "presentation": "media_marketing",
    "news_article": "media_marketing",
    "budget": "financial_operational",
    "invoice": "financial_operational",
    "specification": "financial_operational",
    "email": "correspondence",
    "letter": "correspondence",
    "memo": "correspondence",
    "form": "administrative",
    "questionnaire": "administrative",
    "file_folder": "administrative",
    "resume": "candidate_profile",
    "scientific_publication": "scientific",
    "scientific_report": "scientific",
    "handwritten": "misc_notes",
}


def _compact_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def normalize_rvl_label(raw_label: str) -> str:
    label = raw_label.lower().strip()
    label = label.replace("-", "_").replace(" ", "_")
    label = re.sub(r"_+", "_", label).strip("_")
    compact = _compact_key(label)
    return RVL_LABEL_ALIASES.get(compact, label)


def infer_rvl_doc_family(label: str) -> str:
    normalized = normalize_rvl_label(label)
    return RVL_DOC_FAMILY_MAP.get(normalized, "other")


def iter_rvl_files(root_dir: Path, extensions: Sequence[str]) -> Iterable[Tuple[Path, str]]:
    allowed = normalize_extensions(extensions)
    for class_dir in sorted(path for path in root_dir.iterdir() if path.is_dir()):
        for file_path in class_dir.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in allowed:
                yield file_path, class_dir.name


def build_rvl_cdip_metadata(
    source_dir: Path,
    output_dir: Path,
    val_ratio: float = 0.1,
    test_ratio: float = 0.1,
    random_seed: int = 42,
    min_samples_per_label: int = 1,
    extensions: Sequence[str] = tuple(sorted(DEFAULT_EXTENSIONS)),
) -> pd.DataFrame:
    if val_ratio < 0 or test_ratio < 0:
        raise ValueError("val_ratio and test_ratio must be >= 0.")
    if val_ratio + test_ratio >= 1:
        raise ValueError("val_ratio + test_ratio must be < 1.")
    if min_samples_per_label < 1:
        raise ValueError("min_samples_per_label must be >= 1.")

    rows: List[Dict[str, str]] = []
    for file_path, raw_label in iter_rvl_files(source_dir, extensions):
        normalized_label = normalize_rvl_label(raw_label)
        rows.append(
            {
                "filename": file_path.name,
                "filepath": str(file_path.resolve()),
                "label_raw": raw_label,
                "label": normalized_label,
                "doc_family": infer_rvl_doc_family(normalized_label),
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = output_dir / "metadata.csv"
    labels_path = output_dir / "labels.csv"
    aliases_path = output_dir / "raw_to_normalized_labels.csv"

    df = pd.DataFrame(rows)
    if df.empty:
        pd.DataFrame(columns=["filename", "filepath", "label_raw", "label", "doc_family", "label_id", "split"]).to_csv(
            metadata_path, index=False
        )
        pd.DataFrame(columns=["label_id", "label"]).to_csv(labels_path, index=False)
        pd.DataFrame(columns=["label_raw", "label"]).to_csv(aliases_path, index=False)
        logger.warning("No RVL-CDIP files found. Wrote empty metadata to %s", metadata_path)
        return df

    if min_samples_per_label > 1:
        counts = df["label"].value_counts()
        keep = set(counts[counts >= min_samples_per_label].index.tolist())
        removed = len(df) - int(df["label"].isin(keep).sum())
        df = df[df["label"].isin(keep)].copy()
        if removed > 0:
            logger.info("Removed %d samples from labels below min_samples_per_label.", removed)

    if df.empty:
        pd.DataFrame(columns=["filename", "filepath", "label_raw", "label", "doc_family", "label_id", "split"]).to_csv(
            metadata_path, index=False
        )
        pd.DataFrame(columns=["label_id", "label"]).to_csv(labels_path, index=False)
        pd.DataFrame(columns=["label_raw", "label"]).to_csv(aliases_path, index=False)
        logger.warning("No RVL-CDIP files left after filtering. Wrote empty metadata to %s", metadata_path)
        return df

    labels = sorted(df["label"].unique().tolist())
    label_to_id = {label: idx for idx, label in enumerate(labels)}
    df["label_id"] = df["label"].map(label_to_id)
    df = assign_stratified_splits(
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
        "RVL-CDIP metadata written: %s (total=%d train=%d val=%d test=%d labels=%d)",
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
        description="Build normalized metadata for RVL-CDIP."
    )
    parser.add_argument(
        "--source_dir",
        type=str,
        default="ai_ml_services/datasets/raw_dataset/RVL-CDIP",
        help="Root directory containing RVL-CDIP class folders.",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="ai_ml_services/datasets/processed/rvl_cdip",
        help="Directory where metadata files are written.",
    )
    parser.add_argument(
        "--val_ratio",
        type=float,
        default=0.1,
        help="Validation split ratio per label.",
    )
    parser.add_argument(
        "--test_ratio",
        type=float,
        default=0.1,
        help="Test split ratio per label.",
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
        help="Random seed used for split assignment.",
    )
    parser.add_argument(
        "--extensions",
        nargs="*",
        default=sorted(DEFAULT_EXTENSIONS),
        help="Allowed file extensions (example: .tif .jpg).",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    build_rvl_cdip_metadata(
        source_dir=Path(args.source_dir),
        output_dir=Path(args.output_dir),
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        random_seed=args.random_seed,
        min_samples_per_label=args.min_samples_per_label,
        extensions=args.extensions,
    )


if __name__ == "__main__":
    main()
