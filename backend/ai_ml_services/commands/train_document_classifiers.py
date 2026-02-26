from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import joblib
import numpy as np
import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ai_ml_services.document_classification.features import DocumentFeatureExtractor


def _resolve_path(raw_path: str) -> Path:
    path = Path(str(raw_path))
    if not path.is_absolute():
        path = Path(settings.BASE_DIR) / path
    return path


@dataclass
class DatasetSplit:
    train_df: pd.DataFrame
    eval_df: pd.DataFrame
    eval_split_name: str


class Command(BaseCommand):
    help = "Train RVL-CDIP and MIDV-500 document-type classifiers from metadata files."
    requires_system_checks: list[str] = []

    def add_arguments(self, parser):
        parser.add_argument("--seed", type=int, default=42)
        parser.add_argument("--image-size", type=int, default=128)
        parser.add_argument("--hist-bins", type=int, default=32)

        parser.add_argument(
            "--rvl-metadata",
            type=str,
            default="ai_ml_services/datasets/processed/rvl_cdip/metadata.csv",
            help="Path to RVL-CDIP metadata.csv.",
        )
        parser.add_argument(
            "--midv-metadata",
            type=str,
            default="ai_ml_services/datasets/processed/midv500/metadata.csv",
            help="Path to MIDV-500 metadata.csv.",
        )
        parser.add_argument(
            "--rvl-output-model",
            type=str,
            default=str(
                getattr(
                    settings,
                    "AI_ML_RVL_CDIP_MODEL_PATH",
                    Path(getattr(settings, "MODEL_PATH", Path(settings.BASE_DIR) / "models"))
                    / "rvl_cdip_classifier.pkl",
                )
            ),
            help="Path for serialized RVL classifier artifact.",
        )
        parser.add_argument(
            "--midv-output-model",
            type=str,
            default=str(
                getattr(
                    settings,
                    "AI_ML_MIDV500_MODEL_PATH",
                    Path(getattr(settings, "MODEL_PATH", Path(settings.BASE_DIR) / "models"))
                    / "midv500_classifier.pkl",
                )
            ),
            help="Path for serialized MIDV classifier artifact.",
        )
        parser.add_argument(
            "--report-path",
            type=str,
            default=str(
                Path(getattr(settings, "MODEL_PATH", Path(settings.BASE_DIR) / "models"))
                / "document_classifier_training_report.json"
            ),
            help="Path for JSON training report.",
        )
        parser.add_argument(
            "--midv-source-types",
            nargs="*",
            default=["frame", "template"],
            help="MIDV source_type values to include (from metadata source_type column).",
        )
        parser.add_argument("--rvl-max-train", type=int, default=0, help="Cap RVL train rows (0=no cap).")
        parser.add_argument("--rvl-max-eval", type=int, default=0, help="Cap RVL eval rows (0=no cap).")
        parser.add_argument("--midv-max-train", type=int, default=0, help="Cap MIDV train rows (0=no cap).")
        parser.add_argument("--midv-max-eval", type=int, default=0, help="Cap MIDV eval rows (0=no cap).")
        parser.add_argument("--skip-rvl", action="store_true")
        parser.add_argument("--skip-midv", action="store_true")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        skip_rvl = bool(options["skip_rvl"])
        skip_midv = bool(options["skip_midv"])
        if skip_rvl and skip_midv:
            raise CommandError("At least one dataset must be enabled (remove --skip-rvl or --skip-midv).")

        seed = int(options["seed"])
        np.random.seed(seed)

        feature_extractor = DocumentFeatureExtractor(
            image_size=int(options["image_size"]),
            hist_bins=int(options["hist_bins"]),
        )

        rvl_metadata = _resolve_path(str(options["rvl_metadata"]))
        midv_metadata = _resolve_path(str(options["midv_metadata"]))
        rvl_output = _resolve_path(str(options["rvl_output_model"]))
        midv_output = _resolve_path(str(options["midv_output_model"]))
        report_path = _resolve_path(str(options["report_path"]))

        for out in (rvl_output, midv_output, report_path):
            out.parent.mkdir(parents=True, exist_ok=True)

        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS("Dry run successful."))
            self.stdout.write(f"rvl_metadata={rvl_metadata}")
            self.stdout.write(f"midv_metadata={midv_metadata}")
            self.stdout.write(f"rvl_output_model={rvl_output}")
            self.stdout.write(f"midv_output_model={midv_output}")
            self.stdout.write(f"report_path={report_path}")
            if not skip_rvl:
                self.stdout.write(f"rvl_summary={json.dumps(self._metadata_summary(rvl_metadata), sort_keys=True)}")
            if not skip_midv:
                summary = self._metadata_summary(midv_metadata)
                self.stdout.write(f"midv_summary={json.dumps(summary, sort_keys=True)}")
            return

        report: Dict[str, object] = {
            "seed": seed,
            "feature_config": feature_extractor.config(),
            "artifacts": {
                "rvl_model_path": str(rvl_output),
                "midv_model_path": str(midv_output),
            },
        }

        started = time.time()
        if not skip_rvl:
            self.stdout.write("Training RVL-CDIP classifier...")
            report["rvl_cdip"] = self._train_dataset(
                dataset_name="rvl_cdip",
                metadata_path=rvl_metadata,
                output_model_path=rvl_output,
                feature_extractor=feature_extractor,
                seed=seed,
                max_train=int(options["rvl_max_train"]),
                max_eval=int(options["rvl_max_eval"]),
                source_types=None,
            )

        if not skip_midv:
            self.stdout.write("Training MIDV-500 classifier...")
            source_types = [str(value).strip().lower() for value in options["midv_source_types"] if str(value).strip()]
            report["midv500"] = self._train_dataset(
                dataset_name="midv500",
                metadata_path=midv_metadata,
                output_model_path=midv_output,
                feature_extractor=feature_extractor,
                seed=seed,
                max_train=int(options["midv_max_train"]),
                max_eval=int(options["midv_max_eval"]),
                source_types=source_types or None,
            )

        report["runtime_seconds"] = round(time.time() - started, 3)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Training report written to {report_path}"))

    def _metadata_summary(self, metadata_path: Path) -> Dict[str, object]:
        metadata = self._load_metadata(metadata_path)
        summary: Dict[str, object] = {
            "rows": int(len(metadata)),
            "labels": int(metadata["label"].nunique()) if "label" in metadata.columns else 0,
        }
        if "split" in metadata.columns:
            summary["split_counts"] = {
                str(k): int(v)
                for k, v in metadata["split"].astype(str).str.lower().value_counts().to_dict().items()
            }
        if "source_type" in metadata.columns:
            summary["source_type_counts"] = {
                str(k): int(v)
                for k, v in metadata["source_type"].astype(str).str.lower().value_counts().to_dict().items()
            }
        return summary

    @staticmethod
    def _load_metadata(metadata_path: Path) -> pd.DataFrame:
        if not metadata_path.exists():
            raise CommandError(f"metadata file not found: {metadata_path}")
        metadata = pd.read_csv(metadata_path)
        required_cols = {"filepath", "label"}
        missing = required_cols.difference(metadata.columns)
        if missing:
            raise CommandError(
                f"metadata file missing required columns {sorted(missing)}: {metadata_path}"
            )
        if metadata.empty:
            raise CommandError(f"metadata file is empty: {metadata_path}")
        return metadata

    @staticmethod
    def _ensure_splits(metadata: pd.DataFrame, seed: int) -> pd.DataFrame:
        result = metadata.copy()
        if "split" in result.columns:
            split_series = result["split"].astype(str).str.lower()
            if (split_series == "train").sum() > 0 and split_series.isin({"val", "test"}).sum() > 0:
                result["split"] = split_series
                return result

        labels = result["label"].astype(str)
        if labels.nunique() < 2:
            raise CommandError("At least 2 classes are required to create train/eval split.")

        train_idx, eval_idx = train_test_split(
            np.arange(len(result)),
            test_size=0.2,
            random_state=seed,
            stratify=labels.values,
        )
        result["split"] = "train"
        result.loc[eval_idx, "split"] = "val"
        return result

    @staticmethod
    def _cap_rows(df: pd.DataFrame, max_rows: int, seed: int) -> pd.DataFrame:
        if max_rows <= 0 or len(df) <= max_rows:
            return df
        labels = df["label"].astype(str)
        if labels.nunique() > 1 and max_rows >= labels.nunique():
            kept_idx, _ = train_test_split(
                np.arange(len(df)),
                train_size=max_rows,
                random_state=seed,
                stratify=labels.values,
            )
            return df.iloc[kept_idx].reset_index(drop=True)
        rng = np.random.default_rng(seed)
        chosen = rng.choice(np.arange(len(df)), size=max_rows, replace=False)
        return df.iloc[np.sort(chosen)].reset_index(drop=True)

    @staticmethod
    def _apply_source_filter(metadata: pd.DataFrame, source_types: Sequence[str] | None) -> pd.DataFrame:
        if not source_types:
            return metadata
        if "source_type" not in metadata.columns:
            raise CommandError("Requested source_type filtering but metadata has no source_type column.")
        allowed = {value.strip().lower() for value in source_types if value.strip()}
        if not allowed:
            return metadata
        filtered = metadata[metadata["source_type"].astype(str).str.lower().isin(allowed)].copy()
        if filtered.empty:
            raise CommandError(f"No rows left after source_type filter: {sorted(allowed)}")
        return filtered

    @staticmethod
    def _split_frames(metadata: pd.DataFrame) -> DatasetSplit:
        split_series = metadata["split"].astype(str).str.lower()
        train_df = metadata[split_series == "train"].copy()
        if train_df.empty:
            raise CommandError("No train rows found in metadata.")

        eval_df = metadata[split_series.isin({"val", "test"})].copy()
        eval_split_name = "val_or_test"
        if eval_df.empty:
            eval_df = train_df.copy()
            eval_split_name = "train"

        return DatasetSplit(
            train_df=train_df.reset_index(drop=True),
            eval_df=eval_df.reset_index(drop=True),
            eval_split_name=eval_split_name,
        )

    def _extract_matrix(
        self,
        metadata: pd.DataFrame,
        feature_extractor: DocumentFeatureExtractor,
    ) -> Tuple[np.ndarray, np.ndarray, int]:
        features: List[np.ndarray] = []
        labels: List[str] = []
        skipped = 0
        for row in metadata.itertuples(index=False):
            feature = feature_extractor.extract_from_path(Path(str(row.filepath)))
            if feature is None:
                skipped += 1
                continue
            features.append(feature)
            labels.append(str(row.label))

        if not features:
            raise CommandError("No usable images were loaded from metadata.")

        X = np.asarray(features, dtype=np.float32)
        y = np.asarray(labels, dtype=object)
        return X, y, skipped

    @staticmethod
    def _build_classifier(seed: int) -> Pipeline:
        return Pipeline(
            steps=[
                ("scaler", StandardScaler(with_mean=False)),
                (
                    "clf",
                    SGDClassifier(
                        loss="log_loss",
                        max_iter=2000,
                        tol=1e-3,
                        random_state=seed,
                        class_weight="balanced",
                    ),
                ),
            ]
        )

    @staticmethod
    def _evaluate(model: Pipeline, X: np.ndarray, y_true: np.ndarray) -> Dict[str, float]:
        y_pred = model.predict(X)
        metrics = {
            "accuracy": round(float(accuracy_score(y_true, y_pred)), 6),
            "macro_f1": round(float(f1_score(y_true, y_pred, average="macro", zero_division=0)), 6),
        }
        return metrics

    def _train_dataset(
        self,
        dataset_name: str,
        metadata_path: Path,
        output_model_path: Path,
        feature_extractor: DocumentFeatureExtractor,
        seed: int,
        max_train: int,
        max_eval: int,
        source_types: Sequence[str] | None,
    ) -> Dict[str, object]:
        metadata = self._load_metadata(metadata_path)
        metadata = self._apply_source_filter(metadata, source_types=source_types)
        metadata = self._ensure_splits(metadata, seed=seed)
        split = self._split_frames(metadata)

        train_df = self._cap_rows(split.train_df, max_rows=max_train, seed=seed)
        eval_df = self._cap_rows(split.eval_df, max_rows=max_eval, seed=seed)

        train_X, train_y, train_skipped = self._extract_matrix(train_df, feature_extractor=feature_extractor)
        eval_X, eval_y, eval_skipped = self._extract_matrix(eval_df, feature_extractor=feature_extractor)

        if len(np.unique(train_y)) < 2:
            raise CommandError(
                f"{dataset_name}: training set has fewer than 2 classes after filtering/sampling."
            )

        model = self._build_classifier(seed=seed)
        model.fit(train_X, train_y)
        eval_metrics = self._evaluate(model, eval_X, eval_y)

        artifact = {
            "dataset_name": dataset_name,
            "feature_config": feature_extractor.config(),
            "classes": sorted(np.unique(train_y).tolist()),
            "model": model,
        }
        joblib.dump(artifact, output_model_path)

        result: Dict[str, object] = {
            "metadata_path": str(metadata_path),
            "output_model_path": str(output_model_path),
            "class_count": int(len(np.unique(train_y))),
            "train_rows": int(len(train_df)),
            "eval_rows": int(len(eval_df)),
            "train_images_used": int(len(train_X)),
            "eval_images_used": int(len(eval_X)),
            "train_images_skipped": int(train_skipped),
            "eval_images_skipped": int(eval_skipped),
            "eval_split": split.eval_split_name,
            "metrics": eval_metrics,
        }
        if source_types:
            result["source_types"] = list(source_types)
        return result
