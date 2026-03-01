from __future__ import annotations

import json
import logging
import random
import shutil
import time
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import cv2
import numpy as np
import pandas as pd
import torch
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from pdf2image import convert_from_path
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader

from ai_ml_services.authenticity.cnn_detector import create_model
from ai_ml_services.datasets.fraud_data_generator import FraudDatasetGenerator
from ai_ml_services.datasets.generate_forgeries import (
    SUPPORTED_FORGERY_TYPES,
    ForgeryGenerator,
)
from ai_ml_services.datasets.pytorch_loaders import DocumentAuthenticityDataset
from ai_ml_services.fraud.fraud_detector import FraudDetector
from ai_ml_services.signature.train import train_signature_model
from ai_ml_services.utils.pdf import pdf2image_kwargs

logger = logging.getLogger(__name__)
DEFAULT_FORGERY_TYPES: Tuple[str, ...] = ("copy_move", "resampling", "jpeg")
DEFAULT_PDF_CONVERSION_WARNING_LIMIT = 5


def _resolve_output_path(raw_path: str) -> Path:
    path = Path(str(raw_path))
    if not path.is_absolute():
        path = Path(settings.BASE_DIR) / path
    return path


class Command(BaseCommand):
    help = "Train AI/ML models and write artifacts to configured paths."
    requires_system_checks: list[str] = []

    def add_arguments(self, parser):
        parser.add_argument("--seed", type=int, default=42)
        parser.add_argument("--auth-epochs", type=int, default=12)
        parser.add_argument("--tf-epochs", type=int, default=10)
        parser.add_argument("--batch-size", type=int, default=12)
        parser.add_argument("--num-workers", type=int, default=0)
        parser.add_argument("--target-authentic-images", type=int, default=120)
        parser.add_argument("--forgeries-per-image", type=int, default=3)
        parser.add_argument(
            "--forgery-types",
            nargs="+",
            default=list(DEFAULT_FORGERY_TYPES),
            help=f"Forgery types to generate. Allowed: {', '.join(sorted(SUPPORTED_FORGERY_TYPES))}",
        )
        parser.add_argument("--copy-move-regions", type=int, default=1)
        parser.add_argument("--jpeg-quality-min", type=int, default=55)
        parser.add_argument("--jpeg-quality-max", type=int, default=85)
        parser.add_argument(
            "--verify-forgery-determinism",
            action="store_true",
            help="Assert deterministic forgery generation using the configured seed before training.",
        )
        parser.add_argument("--max-auth-samples", type=int, default=320)
        parser.add_argument(
            "--metadata-file",
            type=str,
            default="",
            help="Optional path to an existing authenticity metadata.csv to use directly.",
        )
        parser.add_argument("--fraud-samples", type=int, default=10000)
        parser.add_argument("--fraud-ratio", type=float, default=0.18)
        parser.add_argument(
            "--signature-metadata-file",
            type=str,
            default="",
            help="Optional path to signature metadata.csv for dedicated signature model training.",
        )
        parser.add_argument("--signature-estimators", type=int, default=300)
        parser.add_argument("--device", type=str, default="auto", choices=["auto", "cpu", "cuda"])
        parser.add_argument("--workspace", type=str, default=".tmp_ai_training")
        parser.add_argument("--keep-workspace", action="store_true")
        parser.set_defaults(freeze_backbone=True, auth_pretrained_backbone=True)
        parser.add_argument("--freeze-backbone", dest="freeze_backbone", action="store_true")
        parser.add_argument("--no-freeze-backbone", dest="freeze_backbone", action="store_false")
        parser.add_argument(
            "--auth-pretrained-backbone",
            dest="auth_pretrained_backbone",
            action="store_true",
            help="Use ImageNet pretrained weights for authenticity ResNet backbone.",
        )
        parser.add_argument(
            "--no-auth-pretrained-backbone",
            dest="auth_pretrained_backbone",
            action="store_false",
            help="Train authenticity ResNet backbone from random initialization.",
        )
        parser.add_argument("--skip-authenticity", action="store_true")
        parser.add_argument("--skip-fraud", action="store_true")
        parser.add_argument("--skip-signature", action="store_true")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        started = time.time()
        run_authenticity_training = not bool(options.get("skip_authenticity", False))
        self._set_seeds(
            int(options["seed"]),
            include_tensorflow=(run_authenticity_training and not bool(options.get("dry_run", False))),
        )
        device = self._select_device(options["device"])
        forgery_types = self._normalize_forgery_types(options.get("forgery_types"))
        copy_move_regions = int(options.get("copy_move_regions", 1))
        jpeg_quality_min = int(options.get("jpeg_quality_min", 55))
        jpeg_quality_max = int(options.get("jpeg_quality_max", 85))
        verify_forgery_determinism = bool(options.get("verify_forgery_determinism", False))

        if not bool(options.get("skip_authenticity", False)):
            self._validate_forgery_profile(
                forgery_types=forgery_types,
                copy_move_regions=copy_move_regions,
                jpeg_quality_min=jpeg_quality_min,
                jpeg_quality_max=jpeg_quality_max,
            )

        h5_path = _resolve_output_path(getattr(settings, "AI_ML_AUTHENTICITY_MODEL_PATH"))
        pth_path = _resolve_output_path(getattr(settings, "AI_ML_AUTHENTICITY_TORCH_MODEL_PATH"))
        fraud_path = _resolve_output_path(getattr(settings, "AI_ML_FRAUD_MODEL_PATH"))
        signature_path = _resolve_output_path(getattr(settings, "AI_ML_SIGNATURE_MODEL_PATH"))
        workspace = _resolve_output_path(options["workspace"])

        for path in (h5_path, pth_path, fraud_path, signature_path):
            path.parent.mkdir(parents=True, exist_ok=True)
        workspace.mkdir(parents=True, exist_ok=True)

        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS("Dry run successful."))
            self.stdout.write(f"device={device}")
            self.stdout.write(f"h5_path={h5_path}")
            self.stdout.write(f"pth_path={pth_path}")
            self.stdout.write(f"fraud_path={fraud_path}")
            self.stdout.write(f"signature_path={signature_path}")
            self.stdout.write(f"workspace={workspace}")
            self.stdout.write(
                "forgery_profile="
                f"{','.join(forgery_types)} "
                f"(copy_move_regions={copy_move_regions}, "
                f"jpeg_quality={jpeg_quality_min}-{jpeg_quality_max}, "
                f"verify_determinism={verify_forgery_determinism})"
            )
            return

        report: Dict[str, object] = {
            "seed": int(options["seed"]),
            "device": device,
            "artifacts": {
                "authenticity_h5": str(h5_path),
                "authenticity_pth": str(pth_path),
                "fraud_pkl": str(fraud_path),
                "signature_pkl": str(signature_path),
            },
        }

        try:
            if not options["skip_authenticity"]:
                metadata_file = str(options.get("metadata_file") or "").strip()
                if metadata_file:
                    metadata_path = _resolve_output_path(metadata_file)
                    if not metadata_path.exists():
                        raise CommandError(f"metadata file not found: {metadata_path}")
                    self.stdout.write(f"Using provided authenticity metadata: {metadata_path}")
                    dataset_meta = self._summarize_metadata(metadata_path, seed=int(options["seed"]))
                else:
                    self.stdout.write("Preparing authenticity dataset...")
                    metadata_path, dataset_meta = self._prepare_authenticity_dataset(
                        workspace=workspace,
                        target_authentic=int(options["target_authentic_images"]),
                        forgeries_per_image=int(options["forgeries_per_image"]),
                        forgery_types=forgery_types,
                        copy_move_regions=copy_move_regions,
                        jpeg_quality_min=jpeg_quality_min,
                        jpeg_quality_max=jpeg_quality_max,
                        verify_forgery_determinism=verify_forgery_determinism,
                        max_samples=int(options["max_auth_samples"]),
                        seed=int(options["seed"]),
                    )
                report["authenticity_dataset"] = dataset_meta

                self.stdout.write("Training PyTorch authenticity model...")
                pt_metrics = self._train_authenticity_pytorch(
                    metadata_path=metadata_path,
                    output_path=pth_path,
                    device=device,
                    epochs=int(options["auth_epochs"]),
                    batch_size=int(options["batch_size"]),
                    num_workers=int(options["num_workers"]),
                    freeze_backbone=bool(options["freeze_backbone"]),
                    pretrained_backbone=bool(options.get("auth_pretrained_backbone", True)),
                )
                report["authenticity_pytorch"] = pt_metrics

                self.stdout.write("Training TensorFlow authenticity model...")
                tf_metrics = self._train_authenticity_tensorflow(
                    metadata_path=metadata_path,
                    output_path=h5_path,
                    epochs=int(options["tf_epochs"]),
                    seed=int(options["seed"]),
                )
                report["authenticity_tensorflow"] = tf_metrics

            if not options["skip_fraud"]:
                self.stdout.write("Training fraud model...")
                fraud_metrics = self._train_fraud_model(
                    output_path=fraud_path,
                    n_samples=int(options["fraud_samples"]),
                    fraud_ratio=float(options["fraud_ratio"]),
                    seed=int(options["seed"]),
                )
                report["fraud"] = fraud_metrics

            if not options.get("skip_signature"):
                signature_metadata_file = str(
                    options.get("signature_metadata_file") or ""
                ).strip()
                if signature_metadata_file:
                    signature_metadata_path = _resolve_output_path(signature_metadata_file)
                    if not signature_metadata_path.exists():
                        raise CommandError(
                            f"signature metadata file not found: {signature_metadata_path}"
                        )
                    self.stdout.write("Training signature model...")
                    report["signature"] = self._train_signature_model(
                        metadata_path=signature_metadata_path,
                        output_path=signature_path,
                        seed=int(options["seed"]),
                        n_estimators=int(options["signature_estimators"]),
                    )
                else:
                    report["signature"] = {
                        "status": "skipped",
                        "reason": "signature_metadata_file_not_provided",
                    }

            report["duration_seconds"] = round(time.time() - started, 2)
            report_path = fraud_path.parent / "training_report.json"
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"Training completed in {report['duration_seconds']}s"))
            self.stdout.write(self.style.SUCCESS(f"Report: {report_path}"))

        finally:
            if not options["keep_workspace"] and workspace.exists():
                shutil.rmtree(workspace, ignore_errors=True)

    @staticmethod
    def _set_seeds(seed: int, include_tensorflow: bool = True) -> None:
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        if include_tensorflow:
            try:
                import tensorflow as tf

                tf.random.set_seed(seed)
            except ModuleNotFoundError:
                pass

    @staticmethod
    def _select_device(mode: str) -> str:
        if mode == "cpu":
            return "cpu"
        if mode == "cuda":
            if not torch.cuda.is_available():
                raise CommandError("CUDA requested but not available.")
            return "cuda"
        return "cuda" if torch.cuda.is_available() else "cpu"

    @staticmethod
    def _normalize_forgery_types(raw_types: Sequence[str] | None) -> Tuple[str, ...]:
        if raw_types is None:
            return DEFAULT_FORGERY_TYPES
        if isinstance(raw_types, str):
            raw_types = [raw_types]

        normalized: List[str] = []
        for value in raw_types:
            for token in str(value).split(","):
                item = token.strip().lower()
                if item:
                    normalized.append(item)
        return tuple(normalized) if normalized else DEFAULT_FORGERY_TYPES

    @staticmethod
    def _validate_forgery_profile(
        forgery_types: Sequence[str],
        copy_move_regions: int,
        jpeg_quality_min: int,
        jpeg_quality_max: int,
    ) -> None:
        unsupported = sorted(set(forgery_types).difference(SUPPORTED_FORGERY_TYPES))
        if unsupported:
            raise CommandError(
                f"Unsupported forgery types: {unsupported}. "
                f"Allowed: {sorted(SUPPORTED_FORGERY_TYPES)}"
            )
        if copy_move_regions < 1:
            raise CommandError("--copy-move-regions must be >= 1.")
        if jpeg_quality_min < 1 or jpeg_quality_min > 100:
            raise CommandError("--jpeg-quality-min must be in [1, 100].")
        if jpeg_quality_max < 1 or jpeg_quality_max > 100:
            raise CommandError("--jpeg-quality-max must be in [1, 100].")
        if jpeg_quality_min > jpeg_quality_max:
            raise CommandError("--jpeg-quality-min cannot be greater than --jpeg-quality-max.")

    @staticmethod
    def _generate_forgeries_for_image(
        image: np.ndarray,
        forgeries_per_image: int,
        forgery_types: Sequence[str],
        copy_move_regions: int,
        jpeg_quality_min: int,
        jpeg_quality_max: int,
        seed: int,
        type_offset: int = 0,
    ) -> List[np.ndarray]:
        generator = ForgeryGenerator(seed=seed)
        variants: List[np.ndarray] = []
        total_variants = max(1, int(forgeries_per_image))
        for idx in range(total_variants):
            forgery_type = forgery_types[(type_offset + idx) % len(forgery_types)]
            if forgery_type == "copy_move":
                variant = generator.copy_move_forgery(image, num_regions=copy_move_regions)
            elif forgery_type == "resampling":
                variant = generator.resampling_forgery(image)
            else:
                quality = generator.rng.randint(jpeg_quality_min, jpeg_quality_max)
                variant = generator.jpeg_compression_attack(image, quality=quality)
            variants.append(variant)
        return variants

    def _assert_forgery_determinism(
        self,
        image_path: Path,
        forgeries_per_image: int,
        forgery_types: Sequence[str],
        copy_move_regions: int,
        jpeg_quality_min: int,
        jpeg_quality_max: int,
        seed: int,
    ) -> None:
        image = cv2.imread(str(image_path))
        if image is None:
            raise CommandError(
                f"Cannot run determinism check. Unable to read image: {image_path}"
            )

        first_run = self._generate_forgeries_for_image(
            image=image,
            forgeries_per_image=forgeries_per_image,
            forgery_types=forgery_types,
            copy_move_regions=copy_move_regions,
            jpeg_quality_min=jpeg_quality_min,
            jpeg_quality_max=jpeg_quality_max,
            seed=seed,
            type_offset=seed,
        )
        second_run = self._generate_forgeries_for_image(
            image=image,
            forgeries_per_image=forgeries_per_image,
            forgery_types=forgery_types,
            copy_move_regions=copy_move_regions,
            jpeg_quality_min=jpeg_quality_min,
            jpeg_quality_max=jpeg_quality_max,
            seed=seed,
            type_offset=seed,
        )

        for idx, (first, second) in enumerate(zip(first_run, second_run)):
            if not np.array_equal(first, second):
                raise CommandError(
                    "Forgery determinism check failed "
                    f"for sample index {idx} at seed {seed}."
                )

    def _prepare_authenticity_dataset(
        self,
        workspace: Path,
        target_authentic: int,
        forgeries_per_image: int,
        forgery_types: Sequence[str],
        copy_move_regions: int,
        jpeg_quality_min: int,
        jpeg_quality_max: int,
        verify_forgery_determinism: bool,
        max_samples: int,
        seed: int,
    ) -> Tuple[Path, Dict[str, object]]:
        auth_dir = workspace / "authentic"
        forged_dir = workspace / "forged"
        auth_dir.mkdir(parents=True, exist_ok=True)
        forged_dir.mkdir(parents=True, exist_ok=True)

        auth_count = self._extract_pdf_pages(auth_dir=auth_dir, target=target_authentic)
        if auth_count < target_authentic:
            self._create_synthetic_authentic(auth_dir=auth_dir, start=auth_count, target=target_authentic)
            auth_count = target_authentic

        authentic_files = sorted(auth_dir.glob("*.png"))
        if verify_forgery_determinism and authentic_files:
            self._assert_forgery_determinism(
                image_path=authentic_files[0],
                forgeries_per_image=forgeries_per_image,
                forgery_types=forgery_types,
                copy_move_regions=copy_move_regions,
                jpeg_quality_min=jpeg_quality_min,
                jpeg_quality_max=jpeg_quality_max,
                seed=seed,
            )

        forge_count = 0
        for image_index, image_path in enumerate(authentic_files):
            image = cv2.imread(str(image_path))
            if image is None:
                continue

            variants = self._generate_forgeries_for_image(
                image=image,
                forgeries_per_image=forgeries_per_image,
                forgery_types=forgery_types,
                copy_move_regions=copy_move_regions,
                jpeg_quality_min=jpeg_quality_min,
                jpeg_quality_max=jpeg_quality_max,
                seed=seed + image_index,
                type_offset=seed + image_index,
            )
            for variant in variants:
                output = forged_dir / f"forged_{forge_count:06d}.png"
                cv2.imwrite(str(output), variant)
                forge_count += 1

        metadata_rows: List[Dict[str, str]] = []
        for file in sorted(auth_dir.glob("*.png")):
            metadata_rows.append(
                {
                    "filename": file.name,
                    "label": "authentic",
                    "category": "authentic",
                    "filepath": str(file.resolve()),
                }
            )
        for file in sorted(forged_dir.glob("*.png")):
            metadata_rows.append(
                {
                    "filename": file.name,
                    "label": "forged",
                    "category": "forged",
                    "filepath": str(file.resolve()),
                }
            )

        if not metadata_rows:
            raise CommandError("No authenticity samples were generated.")

        metadata = pd.DataFrame(metadata_rows)
        if max_samples > 0 and len(metadata) > max_samples:
            class_frames = []
            per_class = max_samples // 2
            for label in ("authentic", "forged"):
                class_df = metadata[metadata["label"] == label]
                if class_df.empty:
                    continue
                sample_n = min(len(class_df), per_class)
                class_frames.append(class_df.sample(n=sample_n, random_state=seed))
            metadata = pd.concat(class_frames, ignore_index=True).sample(
                frac=1.0, random_state=seed
            )

        labels = (metadata["label"] == "authentic").astype(int).values
        train_idx, val_idx = train_test_split(
            np.arange(len(metadata)),
            test_size=0.2,
            random_state=seed,
            stratify=labels,
        )
        metadata["split"] = "train"
        metadata.loc[val_idx, "split"] = "val"

        metadata_path = workspace / "metadata.csv"
        metadata.to_csv(metadata_path, index=False)

        return metadata_path, {
            "total_samples": int(len(metadata)),
            "authentic_samples": int((metadata["label"] == "authentic").sum()),
            "forged_samples": int((metadata["label"] == "forged").sum()),
            "train_samples": int((metadata["split"] == "train").sum()),
            "val_samples": int((metadata["split"] == "val").sum()),
            "forgery_types": ",".join(forgery_types),
            "copy_move_regions": int(copy_move_regions),
            "jpeg_quality_range": f"{jpeg_quality_min}-{jpeg_quality_max}",
            "determinism_checked": bool(verify_forgery_determinism),
        }

    @staticmethod
    def _summarize_metadata(metadata_path: Path, seed: int) -> Dict[str, int]:
        metadata = pd.read_csv(metadata_path)
        required_cols = {"filepath", "label"}
        missing = required_cols.difference(metadata.columns)
        if missing:
            raise CommandError(
                f"metadata file missing required columns: {sorted(missing)}"
            )

        if "split" not in metadata.columns:
            labels = (metadata["label"] == "authentic").astype(int).values
            train_idx, val_idx = train_test_split(
                np.arange(len(metadata)),
                test_size=0.2,
                random_state=seed,
                stratify=labels,
            )
            metadata["split"] = "train"
            metadata.loc[val_idx, "split"] = "val"
            metadata.to_csv(metadata_path, index=False)

        return {
            "total_samples": int(len(metadata)),
            "authentic_samples": int((metadata["label"] == "authentic").sum()),
            "forged_samples": int((metadata["label"] == "forged").sum()),
            "train_samples": int((metadata["split"] == "train").sum()),
            "val_samples": int((metadata["split"] == "val").sum()),
        }

    def _extract_pdf_pages(self, auth_dir: Path, target: int) -> int:
        media_root = Path(getattr(settings, "MEDIA_ROOT", Path(settings.BASE_DIR) / "media"))
        pdf_files = sorted((media_root / "documents").rglob("*.pdf"))
        convert_kwargs = pdf2image_kwargs()
        warning_limit = max(
            0,
            int(
                getattr(
                    settings,
                    "AI_ML_PDF_CONVERSION_WARNING_LIMIT",
                    DEFAULT_PDF_CONVERSION_WARNING_LIMIT,
                )
            ),
        )
        count = 0
        conversion_failures = 0
        suppressed_failures = 0
        for pdf in pdf_files:
            if count >= target:
                break
            try:
                pages = convert_from_path(
                    str(pdf),
                    first_page=1,
                    last_page=1,
                    **convert_kwargs,
                )
                if not pages:
                    continue
                out_path = auth_dir / f"auth_{count:06d}.png"
                pages[0].save(out_path)
                count += 1
            except Exception as exc:
                conversion_failures += 1
                if conversion_failures <= warning_limit:
                    logger.warning("Skipping PDF %s due to conversion error: %s", pdf, exc)
                else:
                    suppressed_failures += 1

        if suppressed_failures > 0:
            logger.warning(
                "Suppressed %d additional PDF conversion warnings after first %d failures.",
                suppressed_failures,
                warning_limit,
            )

        if count == 0 and conversion_failures > 0:
            logger.info(
                "No usable PDFs were extracted (%d conversion failures). "
                "Synthetic authenticity samples will be generated.",
                conversion_failures,
            )
        return count

    @staticmethod
    def _create_synthetic_authentic(auth_dir: Path, start: int, target: int) -> None:
        for idx in range(start, target):
            canvas = np.full((720, 1024, 3), 255, dtype=np.uint8)
            cv2.rectangle(canvas, (24, 24), (1000, 696), (32, 32, 32), 2)
            cv2.putText(canvas, "VETTING DOCUMENT", (60, 90), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (20, 20, 20), 2)
            cv2.putText(
                canvas,
                f"Candidate ID: CND-{random.randint(10000, 99999)}",
                (60, 165),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (35, 35, 35),
                2,
            )
            cv2.putText(
                canvas,
                f"Reference: REF-{random.randint(100000, 999999)}",
                (60, 210),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (35, 35, 35),
                2,
            )
            for line in range(10):
                y = 265 + line * 38
                cv2.line(canvas, (65, y), (950, y), (120, 120, 120), 1)

            noise = np.random.normal(0, 3.5, canvas.shape).astype(np.int16)
            noisy = np.clip(canvas.astype(np.int16) + noise, 0, 255).astype(np.uint8)
            cv2.imwrite(str(auth_dir / f"auth_{idx:06d}.png"), noisy)

    def _train_authenticity_pytorch(
        self,
        metadata_path: Path,
        output_path: Path,
        device: str,
        epochs: int,
        batch_size: int,
        num_workers: int,
        freeze_backbone: bool,
        pretrained_backbone: bool,
    ) -> Dict[str, float]:
        metadata = pd.read_csv(metadata_path)
        train_meta = metadata[metadata["split"] == "train"].reset_index(drop=True)
        val_meta = metadata[metadata["split"] == "val"].reset_index(drop=True)
        train_dataset = DocumentAuthenticityDataset(
            metadata_df=train_meta,
            target_size=(224, 224),
            augment=True,
        )
        val_dataset = DocumentAuthenticityDataset(
            metadata_df=val_meta,
            target_size=(224, 224),
            augment=False,
        )
        train_loader = DataLoader(
            train_dataset,
            batch_size=batch_size,
            shuffle=True,
            num_workers=num_workers,
            pin_memory=False,
        )
        val_loader = DataLoader(
            val_dataset,
            batch_size=batch_size,
            shuffle=False,
            num_workers=num_workers,
            pin_memory=False,
        )

        try:
            model = create_model("resnet18", pretrained=pretrained_backbone).to(device)
        except Exception as exc:
            if pretrained_backbone:
                logger.warning(
                    "Failed to initialize pretrained backbone (%s). Falling back to random init.",
                    exc,
                )
                model = create_model("resnet18", pretrained=False).to(device)
            else:
                raise

        if freeze_backbone and hasattr(model, "backbone"):
            for parameter in model.backbone.parameters():
                parameter.requires_grad = False

        trainable_params = [p for p in model.parameters() if p.requires_grad]
        if not trainable_params:
            raise CommandError("No trainable parameters found for authenticity model.")

        optimizer = torch.optim.Adam(trainable_params, lr=2e-4, weight_decay=1e-5)
        criterion = torch.nn.BCELoss(reduction="none")

        authentic_count = int((train_meta["label"].astype(str).str.lower() == "authentic").sum())
        forged_count = max(0, int(len(train_meta) - authentic_count))
        positive_weight = 1.0
        if authentic_count > 0 and forged_count > 0:
            positive_weight = max(1.0, float(forged_count) / float(authentic_count))
        pos_weight_tensor = torch.tensor(float(positive_weight), dtype=torch.float32, device=device)
        one_weight_tensor = torch.tensor(1.0, dtype=torch.float32, device=device)

        if positive_weight > 1.0:
            logger.info(
                "Using authenticity positive class weight %.4f (authentic=%d, forged=%d)",
                positive_weight,
                authentic_count,
                forged_count,
            )

        best = {"f1": -1.0, "acc": 0.0, "epoch": 0, "state": None, "threshold": 0.5}
        for epoch in range(max(1, epochs)):
            model.train()
            for batch in train_loader:
                images, labels = batch[0].to(device), batch[1].float().unsqueeze(1).to(device)
                optimizer.zero_grad()
                out = model(images)
                loss_raw = criterion(out, labels)
                sample_weights = torch.where(labels > 0.5, pos_weight_tensor, one_weight_tensor)
                loss = (loss_raw * sample_weights).mean()
                loss.backward()
                optimizer.step()

            model.eval()
            y_true: List[int] = []
            y_scores: List[float] = []
            with torch.no_grad():
                for batch in val_loader:
                    images, labels = batch[0].to(device), batch[1].float().unsqueeze(1).to(device)
                    out = model(images)
                    scores = out.cpu().numpy().flatten().tolist()
                    truth = labels.int().cpu().numpy().flatten().tolist()
                    y_scores.extend([float(score) for score in scores])
                    y_true.extend(truth)

            if not y_scores:
                continue

            thresholds = np.linspace(0.2, 0.8, 25, dtype=np.float32)
            epoch_best_threshold = 0.5
            epoch_best_f1 = -1.0
            epoch_best_acc = 0.0
            y_true_np = np.asarray(y_true, dtype=np.int32)
            y_scores_np = np.asarray(y_scores, dtype=np.float32)

            for threshold in thresholds:
                preds = (y_scores_np >= float(threshold)).astype(np.int32)
                f1_candidate = float(f1_score(y_true_np, preds, zero_division=0))
                if f1_candidate > epoch_best_f1:
                    epoch_best_f1 = f1_candidate
                    epoch_best_threshold = float(threshold)
                    epoch_best_acc = float(accuracy_score(y_true_np, preds))

            if epoch_best_f1 >= best["f1"]:
                best = {
                    "f1": epoch_best_f1,
                    "acc": epoch_best_acc,
                    "epoch": epoch + 1,
                    "state": {k: v.cpu() for k, v in model.state_dict().items()},
                    "threshold": epoch_best_threshold,
                }

        if best["state"] is None:
            raise CommandError("PyTorch authenticity training did not produce a model state.")

        torch.save(
            {
                "model_state_dict": best["state"],
                "epoch": best["epoch"],
                "metrics": {"val_f1": best["f1"], "val_accuracy": best["acc"]},
                "decision_threshold": best["threshold"],
            },
            output_path,
        )
        return {
            "val_f1": round(best["f1"], 6),
            "val_accuracy": round(best["acc"], 6),
            "best_epoch": int(best["epoch"]),
            "output_path": str(output_path),
            "decision_threshold": round(float(best.get("threshold", 0.5)), 6),
        }

    def _train_authenticity_tensorflow(
        self,
        metadata_path: Path,
        output_path: Path,
        epochs: int,
        seed: int,
    ) -> Dict[str, float]:
        try:
            import tensorflow as tf
        except ModuleNotFoundError as exc:
            raise CommandError("TensorFlow is required to train authenticity .h5 model.") from exc

        metadata = pd.read_csv(metadata_path)
        X: List[np.ndarray] = []
        y: List[int] = []
        for _, row in metadata.iterrows():
            image = cv2.imread(str(row["filepath"]))
            if image is None:
                continue
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            image = cv2.resize(image, (224, 224)).astype("float32") / 255.0
            X.append(image)
            y.append(1 if row["label"] == "authentic" else 0)

        if len(X) < 20:
            raise CommandError("Not enough authenticity images for TensorFlow training.")

        X_np = np.asarray(X, dtype=np.float32)
        y_np = np.asarray(y, dtype=np.float32)
        X_train, X_val, y_train, y_val = train_test_split(
            X_np, y_np, test_size=0.2, random_state=seed, stratify=y_np.astype(int)
        )

        model = tf.keras.Sequential(
            [
                tf.keras.layers.Input(shape=(224, 224, 3)),
                tf.keras.layers.Conv2D(16, 3, activation="relu"),
                tf.keras.layers.MaxPooling2D(),
                tf.keras.layers.Conv2D(32, 3, activation="relu"),
                tf.keras.layers.MaxPooling2D(),
                tf.keras.layers.Conv2D(64, 3, activation="relu"),
                tf.keras.layers.GlobalAveragePooling2D(),
                tf.keras.layers.Dropout(0.3),
                tf.keras.layers.Dense(1, activation="sigmoid"),
            ]
        )
        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
            loss="binary_crossentropy",
            metrics=["accuracy"],
        )
        model.fit(
            X_train,
            y_train,
            validation_data=(X_val, y_val),
            epochs=max(1, epochs),
            batch_size=12,
            verbose=0,
        )
        _, val_acc = model.evaluate(X_val, y_val, verbose=0)
        model.save(str(output_path))

        return {"val_accuracy": round(float(val_acc), 6), "output_path": str(output_path)}

    @staticmethod
    def _train_fraud_model(
        output_path: Path,
        n_samples: int,
        fraud_ratio: float,
        seed: int,
    ) -> Dict[str, float]:
        np.random.seed(seed)
        generator = FraudDatasetGenerator()
        train_df, _test_df = generator.generate_application_data(
            n_samples=max(2000, n_samples),
            fraud_ratio=fraud_ratio,
            random_seed=seed,
        )
        feature_cols = [c for c in train_df.columns if c not in ("application_id", "is_fraud")]
        X_train = train_df[feature_cols].values.astype(np.float32)
        y_train = train_df["is_fraud"].values.astype(np.int64)

        detector = FraudDetector(model_type="random_forest")
        metrics = detector.train(X_train, y_train, feature_names=feature_cols)
        detector.save_model(str(output_path))

        return {
            "f1": round(float(metrics.get("f1", 0.0)), 6),
            "auc": round(float(metrics.get("auc", 0.0)), 6),
            "accuracy": round(float(metrics.get("accuracy", 0.0)), 6),
            "output_path": str(output_path),
        }

    @staticmethod
    def _train_signature_model(
        metadata_path: Path,
        output_path: Path,
        seed: int,
        n_estimators: int,
    ) -> Dict[str, float]:
        metrics = train_signature_model(
            metadata_path=metadata_path,
            output_path=output_path,
            seed=seed,
            n_estimators=n_estimators,
        )
        return metrics
