from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import cv2
import joblib
import numpy as np
import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import LinearSVC

from ai_ml_services.document_classification.features import DocumentFeatureExtractor
from ai_ml_services.utils.path_rebase import infer_backend_root, rebase_moved_backend_path

logger = logging.getLogger(__name__)


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
            "--feature-backend",
            type=str,
            default="hog_histogram",
            choices=["hog_histogram", "resnet18_embedding", "hybrid_hog_resnet"],
            help="Feature backend for document classifiers.",
        )
        parser.add_argument(
            "--feature-device",
            type=str,
            default="auto",
            choices=["auto", "cpu", "cuda"],
            help="Device hint for feature extraction backend.",
        )
        parser.set_defaults(feature_pretrained=True)
        parser.add_argument(
            "--feature-pretrained",
            dest="feature_pretrained",
            action="store_true",
            help="Use pretrained weights for embedding backends when available.",
        )
        parser.add_argument(
            "--no-feature-pretrained",
            dest="feature_pretrained",
            action="store_false",
            help="Disable pretrained weights for embedding backends.",
        )

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
        parser.add_argument(
            "--rvl-label-column",
            type=str,
            default="label",
            help="Label column to train RVL classifier with.",
        )
        parser.add_argument(
            "--midv-label-column",
            type=str,
            default="label",
            help="Label column to train MIDV classifier with.",
        )
        parser.add_argument(
            "--rvl-trainer",
            type=str,
            default="linear",
            choices=["linear", "cnn"],
            help="RVL trainer backend. `linear` uses feature extractor + LinearSVC, `cnn` fine-tunes ResNet18.",
        )
        parser.add_argument("--rvl-cnn-epochs", type=int, default=4)
        parser.add_argument("--rvl-cnn-batch-size", type=int, default=16)
        parser.add_argument("--rvl-cnn-learning-rate", type=float, default=1e-4)
        parser.set_defaults(rvl_cnn_pretrained=True, rvl_cnn_freeze_backbone=True)
        parser.add_argument(
            "--rvl-cnn-pretrained",
            dest="rvl_cnn_pretrained",
            action="store_true",
            help="Use ImageNet pretrained ResNet18 weights for RVL CNN trainer.",
        )
        parser.add_argument(
            "--no-rvl-cnn-pretrained",
            dest="rvl_cnn_pretrained",
            action="store_false",
            help="Disable pretrained weights for RVL CNN trainer.",
        )
        parser.add_argument(
            "--rvl-cnn-freeze-backbone",
            dest="rvl_cnn_freeze_backbone",
            action="store_true",
            help="Freeze ResNet backbone and train classifier head only.",
        )
        parser.add_argument(
            "--no-rvl-cnn-freeze-backbone",
            dest="rvl_cnn_freeze_backbone",
            action="store_false",
            help="Fine-tune full ResNet backbone for RVL CNN trainer.",
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
            backend=str(options.get("feature_backend", "hog_histogram")),
            resnet_pretrained=bool(options.get("feature_pretrained", True)),
            resnet_device=str(options.get("feature_device", "auto")),
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
            self.stdout.write(f"feature_backend={options.get('feature_backend', 'hog_histogram')}")
            self.stdout.write(f"feature_device={options.get('feature_device', 'auto')}")
            self.stdout.write(f"feature_pretrained={bool(options.get('feature_pretrained', True))}")
            self.stdout.write(f"rvl_trainer={options.get('rvl_trainer', 'linear')}")
            self.stdout.write(f"rvl_cnn_epochs={int(options.get('rvl_cnn_epochs', 4))}")
            self.stdout.write(f"rvl_cnn_batch_size={int(options.get('rvl_cnn_batch_size', 16))}")
            self.stdout.write(f"rvl_cnn_learning_rate={float(options.get('rvl_cnn_learning_rate', 1e-4))}")
            self.stdout.write(f"rvl_cnn_pretrained={bool(options.get('rvl_cnn_pretrained', True))}")
            self.stdout.write(f"rvl_cnn_freeze_backbone={bool(options.get('rvl_cnn_freeze_backbone', True))}")
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
                label_column=str(options.get("rvl_label_column") or "label"),
                trainer=str(options.get("rvl_trainer") or "linear"),
                rvl_cnn_epochs=int(options.get("rvl_cnn_epochs", 4)),
                rvl_cnn_batch_size=int(options.get("rvl_cnn_batch_size", 16)),
                rvl_cnn_learning_rate=float(options.get("rvl_cnn_learning_rate", 1e-4)),
                rvl_cnn_pretrained=bool(options.get("rvl_cnn_pretrained", True)),
                rvl_cnn_freeze_backbone=bool(options.get("rvl_cnn_freeze_backbone", True)),
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
                label_column=str(options.get("midv_label_column") or "label"),
                trainer="linear",
                rvl_cnn_epochs=0,
                rvl_cnn_batch_size=0,
                rvl_cnn_learning_rate=0.0,
                rvl_cnn_pretrained=True,
                rvl_cnn_freeze_backbone=True,
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

        backend_root = infer_backend_root(metadata_path)
        original_paths = metadata["filepath"].astype(str)
        resolved_paths = [
            str(rebase_moved_backend_path(raw_path, backend_root=backend_root))
            for raw_path in original_paths
        ]
        metadata = metadata.copy()
        metadata["filepath"] = resolved_paths

        rebased_count = int(sum(orig != resolved for orig, resolved in zip(original_paths, resolved_paths)))
        if rebased_count > 0:
            logger.info("Rebased %d metadata filepaths for %s", rebased_count, metadata_path)

        existing_count = int(metadata["filepath"].map(lambda value: Path(str(value)).exists()).sum())
        if existing_count == 0:
            raise CommandError(
                "No readable filepaths in metadata after path resolution: "
                f"{metadata_path}"
            )

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

    @staticmethod
    def _order_quad_points(points: np.ndarray) -> np.ndarray:
        ordered = np.zeros((4, 2), dtype=np.float32)
        sums = points.sum(axis=1)
        diffs = np.diff(points, axis=1)

        ordered[0] = points[np.argmin(sums)]  # top-left
        ordered[2] = points[np.argmax(sums)]  # bottom-right
        ordered[1] = points[np.argmin(diffs)]  # top-right
        ordered[3] = points[np.argmax(diffs)]  # bottom-left
        return ordered

    def _crop_with_quad(self, image: np.ndarray, quad_points: object) -> np.ndarray | None:
        raw_points = quad_points
        if isinstance(quad_points, str):
            text = quad_points.strip()
            if not text:
                return None
            try:
                raw_points = json.loads(text)
            except Exception:
                return None

        points = np.asarray(raw_points, dtype=np.float32)
        if points.shape != (4, 2):
            return None

        ordered = self._order_quad_points(points)
        width_top = np.linalg.norm(ordered[1] - ordered[0])
        width_bottom = np.linalg.norm(ordered[2] - ordered[3])
        max_width = int(max(width_top, width_bottom))

        height_right = np.linalg.norm(ordered[2] - ordered[1])
        height_left = np.linalg.norm(ordered[3] - ordered[0])
        max_height = int(max(height_right, height_left))

        if max_width < 8 or max_height < 8:
            return None

        destination = np.array(
            [[0, 0], [max_width - 1, 0], [max_width - 1, max_height - 1], [0, max_height - 1]],
            dtype=np.float32,
        )
        matrix = cv2.getPerspectiveTransform(ordered, destination)
        return cv2.warpPerspective(image, matrix, (max_width, max_height))

    def _extract_matrix(
        self,
        metadata: pd.DataFrame,
        feature_extractor: DocumentFeatureExtractor,
    ) -> Tuple[np.ndarray, np.ndarray, int]:
        features: List[np.ndarray] = []
        labels: List[str] = []
        skipped = 0
        for row in metadata.itertuples(index=False):
            image = cv2.imread(str(row.filepath))
            if image is None:
                skipped += 1
                continue

            has_quad = bool(getattr(row, "has_quad", False))
            quad_points = getattr(row, "quad_points", "")
            if has_quad and quad_points:
                cropped = self._crop_with_quad(image=image, quad_points=quad_points)
                if cropped is not None:
                    image = cropped

            feature = feature_extractor.extract_from_image(image)
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
                    LinearSVC(
                        C=1.2,
                        class_weight="balanced",
                        random_state=seed,
                        max_iter=8000,
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

    @staticmethod
    def _preprocess_torch_image(image: np.ndarray, image_size: int = 224):
        import torch

        if image.ndim == 2:
            rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        elif image.shape[2] == 4:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGRA2RGB)
        else:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        resized = cv2.resize(rgb, (image_size, image_size), interpolation=cv2.INTER_AREA)
        tensor = torch.from_numpy(resized.transpose(2, 0, 1)).to(torch.float32) / 255.0
        mean = torch.tensor([0.485, 0.456, 0.406], dtype=torch.float32).view(3, 1, 1)
        std = torch.tensor([0.229, 0.224, 0.225], dtype=torch.float32).view(3, 1, 1)
        tensor = (tensor - mean) / std
        return tensor

    def _prepare_torch_rows(
        self,
        frame: pd.DataFrame,
        class_to_idx: Dict[str, int],
        image_size: int = 224,
    ) -> tuple[list[object], list[int], int]:
        rows = []
        labels = []
        skipped = 0
        for row in frame.itertuples(index=False):
            image = cv2.imread(str(row.filepath))
            if image is None:
                skipped += 1
                continue

            tensor = self._preprocess_torch_image(image=image, image_size=image_size)
            label_str = str(row.label)
            if label_str not in class_to_idx:
                skipped += 1
                continue
            rows.append(tensor)
            labels.append(class_to_idx[label_str])
        return rows, labels, skipped

    @staticmethod
    def _batch_tensors(tensors):
        import torch

        return torch.stack(tensors, dim=0)

    def _train_rvl_cnn_dataset(
        self,
        metadata: pd.DataFrame,
        output_model_path: Path,
        seed: int,
        max_train: int,
        max_eval: int,
        label_column: str,
        epochs: int,
        batch_size: int,
        learning_rate: float,
        pretrained: bool,
        freeze_backbone: bool,
    ) -> Dict[str, object]:
        try:
            import torch
            from torch.utils.data import DataLoader, TensorDataset
            from torchvision import models as tv_models
        except ModuleNotFoundError as exc:
            raise CommandError(
                "RVL CNN trainer requires torch and torchvision."
            ) from exc

        metadata = self._ensure_splits(metadata, seed=seed)
        split = self._split_frames(metadata)

        train_df = self._cap_rows(split.train_df, max_rows=max_train, seed=seed)
        eval_df = self._cap_rows(split.eval_df, max_rows=max_eval, seed=seed)

        classes = sorted(train_df["label"].astype(str).unique().tolist())
        if len(classes) < 2:
            raise CommandError("rvl_cdip: CNN training requires at least 2 classes.")
        class_to_idx = {label: idx for idx, label in enumerate(classes)}

        train_tensors, train_labels, train_skipped = self._prepare_torch_rows(train_df, class_to_idx)
        eval_tensors, eval_labels, eval_skipped = self._prepare_torch_rows(eval_df, class_to_idx)

        if not train_tensors or not eval_tensors:
            raise CommandError("rvl_cdip: no usable tensors for CNN training/evaluation.")

        train_x = self._batch_tensors(train_tensors)
        train_y = torch.tensor(train_labels, dtype=torch.long)
        eval_x = self._batch_tensors(eval_tensors)
        eval_y = torch.tensor(eval_labels, dtype=torch.long)

        train_loader = DataLoader(TensorDataset(train_x, train_y), batch_size=batch_size, shuffle=True)
        eval_loader = DataLoader(TensorDataset(eval_x, eval_y), batch_size=batch_size, shuffle=False)

        if pretrained:
            try:
                model = tv_models.resnet18(weights=tv_models.ResNet18_Weights.DEFAULT)
            except (AttributeError, TypeError):
                model = tv_models.resnet18(pretrained=True)
        else:
            try:
                model = tv_models.resnet18(weights=None)
            except TypeError:
                model = tv_models.resnet18(pretrained=False)

        feature_dim = model.fc.in_features
        model.fc = torch.nn.Linear(feature_dim, len(classes))

        if freeze_backbone:
            for name, param in model.named_parameters():
                if not name.startswith("fc."):
                    param.requires_grad = False

        device = "cuda" if torch.cuda.is_available() else "cpu"
        model.to(device)

        class_counts = np.bincount(train_y.numpy(), minlength=len(classes)).astype(np.float32)
        class_counts[class_counts <= 0] = 1.0
        inv = class_counts.sum() / (class_counts * float(len(classes)))
        criterion = torch.nn.CrossEntropyLoss(weight=torch.tensor(inv, dtype=torch.float32, device=device))

        trainable_params = [p for p in model.parameters() if p.requires_grad]
        if not trainable_params:
            raise CommandError("rvl_cdip: no trainable parameters for CNN trainer.")
        optimizer = torch.optim.Adam(trainable_params, lr=max(1e-6, float(learning_rate)), weight_decay=1e-5)

        best_f1 = -1.0
        best_acc = 0.0
        best_epoch = 0
        best_state = None

        for epoch in range(1, epochs + 1):
            model.train()
            for batch_x, batch_y in train_loader:
                batch_x = batch_x.to(device)
                batch_y = batch_y.to(device)
                optimizer.zero_grad()
                logits = model(batch_x)
                loss = criterion(logits, batch_y)
                loss.backward()
                optimizer.step()

            model.eval()
            y_true = []
            y_pred = []
            with torch.no_grad():
                for batch_x, batch_y in eval_loader:
                    batch_x = batch_x.to(device)
                    logits = model(batch_x)
                    preds = torch.argmax(logits, dim=1).cpu().numpy().tolist()
                    y_pred.extend([int(v) for v in preds])
                    y_true.extend([int(v) for v in batch_y.numpy().tolist()])

            epoch_acc = float(accuracy_score(y_true, y_pred))
            epoch_f1 = float(f1_score(y_true, y_pred, average="macro", zero_division=0))
            if epoch_f1 >= best_f1:
                best_f1 = epoch_f1
                best_acc = epoch_acc
                best_epoch = epoch
                best_state = {k: v.detach().cpu() for k, v in model.state_dict().items()}

        if best_state is None:
            raise CommandError("rvl_cdip: CNN trainer did not produce a model state.")

        checkpoint_path = output_model_path.with_suffix(".pth")
        torch.save(
            {
                "model_state_dict": best_state,
                "classes": classes,
                "metrics": {
                    "accuracy": best_acc,
                    "macro_f1": best_f1,
                    "best_epoch": best_epoch,
                },
                "input_size": 224,
            },
            checkpoint_path,
        )

        artifact = {
            "dataset_name": "rvl_cdip",
            "model_type": "torch_resnet18_classifier",
            "checkpoint_path": str(checkpoint_path),
            "classes": classes,
            "input_size": 224,
            "normalization": {
                "mean": [0.485, 0.456, 0.406],
                "std": [0.229, 0.224, 0.225],
            },
            "feature_config": {
                "type": "torch_resnet18_classifier",
                "trainer": "cnn",
                "pretrained": bool(pretrained),
                "freeze_backbone": bool(freeze_backbone),
            },
        }
        joblib.dump(artifact, output_model_path)

        return {
            "metadata_path": "runtime",
            "output_model_path": str(output_model_path),
            "checkpoint_path": str(checkpoint_path),
            "class_count": int(len(classes)),
            "train_rows": int(len(train_df)),
            "eval_rows": int(len(eval_df)),
            "train_images_used": int(len(train_tensors)),
            "eval_images_used": int(len(eval_tensors)),
            "train_images_skipped": int(train_skipped),
            "eval_images_skipped": int(eval_skipped),
            "eval_split": split.eval_split_name,
            "metrics": {
                "accuracy": round(best_acc, 6),
                "macro_f1": round(best_f1, 6),
            },
            "label_column": label_column,
            "trainer": "cnn",
            "best_epoch": int(best_epoch),
            "device": device,
            "pretrained": bool(pretrained),
            "freeze_backbone": bool(freeze_backbone),
        }

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
        label_column: str,
        trainer: str,
        rvl_cnn_epochs: int,
        rvl_cnn_batch_size: int,
        rvl_cnn_learning_rate: float,
        rvl_cnn_pretrained: bool,
        rvl_cnn_freeze_backbone: bool,
    ) -> Dict[str, object]:
        metadata = self._load_metadata(metadata_path)
        metadata = self._apply_source_filter(metadata, source_types=source_types)
        selected_label_column = (label_column or "label").strip() or "label"
        if selected_label_column not in metadata.columns:
            raise CommandError(
                f"{dataset_name}: requested label column `{selected_label_column}` not found in metadata."
            )
        metadata = metadata.copy()
        metadata["label"] = metadata[selected_label_column].astype(str)

        normalized_trainer = str(trainer or "linear").strip().lower()
        if dataset_name == "rvl_cdip" and normalized_trainer == "cnn":
            return self._train_rvl_cnn_dataset(
                metadata=metadata,
                output_model_path=output_model_path,
                seed=seed,
                max_train=max_train,
                max_eval=max_eval,
                label_column=selected_label_column,
                epochs=max(1, int(rvl_cnn_epochs)),
                batch_size=max(1, int(rvl_cnn_batch_size)),
                learning_rate=float(rvl_cnn_learning_rate),
                pretrained=bool(rvl_cnn_pretrained),
                freeze_backbone=bool(rvl_cnn_freeze_backbone),
            )

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
        result["label_column"] = selected_label_column
        return result

