from __future__ import annotations

import compileall
import importlib
import json
import re
import shutil
from pathlib import Path
from typing import Any, List, Tuple

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


LEGACY_IMPORT_PATTERNS = (
    r"\bfrom config import\b",
    r"\bfrom datasets\.",
    r"\bapps\.ai_services\b",
    r"\bfrom interview\.",
)


class Command(BaseCommand):
    help = (
        "Run AI/ML preflight checks: syntax/import smoke checks plus runtime "
        "configuration, artifact validation, and model quality gates."
    )
    # Avoid unrelated project URL/system-check failures from blocking this targeted check.
    requires_system_checks: list[str] = []

    def add_arguments(self, parser):
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Treat warnings (like missing model artifacts) as failures.",
        )

    def handle(self, *args, **options):
        strict = bool(options.get("strict"))
        ai_ml_dir = Path(settings.BASE_DIR) / "ai_ml_services"
        if not ai_ml_dir.exists():
            module_dir = Path(__file__).resolve().parents[1]
            if module_dir.exists():
                ai_ml_dir = module_dir
            else:
                raise CommandError(f"Directory not found: {ai_ml_dir}")

        errors: List[str] = []
        warnings: List[str] = []

        self.stdout.write(f"Checking syntax in {ai_ml_dir}...")
        compiled_ok = compileall.compile_dir(str(ai_ml_dir), quiet=1)
        if not compiled_ok:
            raise CommandError("Python compilation failed for ai_ml_services.")

        self.stdout.write("Checking for legacy import patterns...")
        findings = self._scan_for_legacy_patterns(ai_ml_dir)
        if findings:
            for file_path, line_no, line_text in findings:
                self.stdout.write(
                    self.style.ERROR(
                        f"{file_path}:{line_no} -> {line_text.strip()}"
                    )
                )
            errors.append(
                f"Found {len(findings)} legacy import pattern violation(s)."
            )

        self.stdout.write("Checking required runtime imports...")
        import_errors = self._check_required_imports()
        errors.extend(import_errors)

        self.stdout.write("Checking runtime configuration...")
        config_errors, config_warnings = self._check_runtime_configuration()
        errors.extend(config_errors)
        warnings.extend(config_warnings)

        self.stdout.write("Checking model artifact paths...")
        warnings.extend(self._check_model_artifacts())

        self.stdout.write("Checking model quality gates...")
        quality_errors, quality_warnings = self._check_model_quality()
        errors.extend(quality_errors)
        warnings.extend(quality_warnings)

        for message in warnings:
            self.stdout.write(self.style.WARNING(f"WARNING: {message}"))
        for message in errors:
            self.stdout.write(self.style.ERROR(f"ERROR: {message}"))

        if errors:
            raise CommandError(
                f"ai_ml_services preflight failed with {len(errors)} error(s)."
            )
        if strict and warnings:
            raise CommandError(
                "ai_ml_services preflight strict mode failed with "
                f"{len(warnings)} warning(s)."
            )

        summary = (
            f"ai_ml_services checks passed"
            f"{' (with warnings)' if warnings else ''}."
        )
        self.stdout.write(self.style.SUCCESS(summary))

    def _scan_for_legacy_patterns(self, base_dir: Path) -> List[Tuple[Path, int, str]]:
        compiled_patterns = [re.compile(pattern) for pattern in LEGACY_IMPORT_PATTERNS]
        findings: List[Tuple[Path, int, str]] = []

        for py_file in base_dir.rglob("*.py"):
            if "__pycache__" in py_file.parts:
                continue

            with py_file.open("r", encoding="utf-8") as handle:
                for line_no, line in enumerate(handle, start=1):
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#"):
                        continue
                    for pattern in compiled_patterns:
                        if pattern.search(line):
                            findings.append((py_file, line_no, line))
                            break

        return findings

    def _check_required_imports(self) -> List[str]:
        required_modules = (
            "ai_ml_services.service",
            "ai_ml_services.utils.tasks",
            "ai_ml_services.authenticity.authenticity_detector",
            "ai_ml_services.fraud.fraud_detector",
            "ai_ml_services.signature.signature_detector",
            "ai_ml_services.ocr.ocr_service",
            "ai_ml_services.interview.websocket_handler",
            "ai_ml_services.video.identity_matcher",
            "ai_ml_services.document_classification.classifier",
        )
        errors: List[str] = []
        for module in required_modules:
            try:
                importlib.import_module(module)
            except Exception as exc:
                errors.append(f"Could not import `{module}`: {exc}")
        return errors

    def _check_runtime_configuration(self) -> Tuple[List[str], List[str]]:
        errors: List[str] = []
        warnings: List[str] = []

        approval = float(getattr(settings, "AI_ML_APPROVAL_THRESHOLD", 85.0))
        manual_review = float(getattr(settings, "AI_ML_MANUAL_REVIEW_THRESHOLD", 70.0))
        if manual_review > approval:
            errors.append(
                "AI_ML_MANUAL_REVIEW_THRESHOLD cannot be greater than "
                "AI_ML_APPROVAL_THRESHOLD."
            )

        consistency_thresholds = getattr(settings, "AI_ML_CONSISTENCY_THRESHOLDS", {}) or {}
        try:
            consistency_approve = float(consistency_thresholds.get("approve", 85.0))
            consistency_review = float(consistency_thresholds.get("manual_review", 70.0))
            if consistency_review > consistency_approve:
                errors.append(
                    "AI_ML_CONSISTENCY_THRESHOLDS.manual_review cannot be greater "
                    "than AI_ML_CONSISTENCY_THRESHOLDS.approve."
                )
        except (TypeError, ValueError):
            errors.append("AI_ML_CONSISTENCY_THRESHOLDS must contain numeric values.")

        service_token = str(getattr(settings, "SERVICE_TOKEN", "") or "").strip()
        if not service_token:
            if settings.DEBUG:
                warnings.append(
                    "SERVICE_TOKEN is empty. Service-to-service interview flows "
                    "will be blocked outside authenticated user sessions."
                )
            else:
                errors.append("SERVICE_TOKEN is required when DEBUG=False.")

        monitor_enabled = bool(getattr(settings, "AI_ML_MONITOR_ENABLED", True))
        monitor_use_redis = bool(getattr(settings, "AI_ML_MONITOR_USE_REDIS", False))
        monitor_redis_url = str(getattr(settings, "AI_ML_MONITOR_REDIS_URL", "") or "")
        if monitor_enabled and monitor_use_redis and not monitor_redis_url:
            errors.append(
                "AI_ML_MONITOR_USE_REDIS=True requires AI_ML_MONITOR_REDIS_URL."
            )

        identity_threshold = float(
            getattr(settings, "AI_ML_IDENTITY_MATCH_THRESHOLD", 0.72)
        )
        if identity_threshold < 0.0 or identity_threshold > 1.0:
            errors.append(
                "AI_ML_IDENTITY_MATCH_THRESHOLD must be between 0.0 and 1.0."
            )

        identity_backend = str(
            getattr(settings, "AI_ML_IDENTITY_EMBEDDING_BACKEND", "auto") or "auto"
        ).strip().lower()
        if identity_backend not in {"auto", "facenet", "deepface"}:
            errors.append(
                "AI_ML_IDENTITY_EMBEDDING_BACKEND must be one of: auto, facenet, deepface."
            )

        identity_sample_rate = int(
            getattr(settings, "AI_ML_IDENTITY_VIDEO_SAMPLE_RATE", 8)
        )
        if identity_sample_rate < 1:
            errors.append("AI_ML_IDENTITY_VIDEO_SAMPLE_RATE must be >= 1.")

        mismatch_confidence = float(
            getattr(settings, "AI_ML_DOC_TYPE_MISMATCH_CONFIDENCE", 0.65)
        )
        if mismatch_confidence < 0.0 or mismatch_confidence > 1.0:
            errors.append(
                "AI_ML_DOC_TYPE_MISMATCH_CONFIDENCE must be between 0.0 and 1.0."
            )

        facenet_available = importlib.util.find_spec("facenet_pytorch") is not None
        deepface_available = importlib.util.find_spec("deepface") is not None
        if identity_backend == "facenet" and not facenet_available:
            warnings.append(
                "AI_ML_IDENTITY_EMBEDDING_BACKEND=facenet but facenet-pytorch is not installed."
            )
        if identity_backend == "deepface" and not deepface_available:
            warnings.append(
                "AI_ML_IDENTITY_EMBEDDING_BACKEND=deepface but deepface is not installed."
            )
        if identity_backend == "auto" and not (facenet_available or deepface_available):
            warnings.append(
                "Identity matching backend is auto, but neither facenet-pytorch nor deepface "
                "is installed."
            )

        if not shutil.which("pdfinfo"):
            try:
                from ai_ml_services.utils.pdf import resolve_poppler_path

                if not resolve_poppler_path():
                    warnings.append(
                        "Poppler/pdfinfo not found. PDF rasterization paths (OCR/CV/training) "
                        "may fail until Poppler is installed or AI_ML_POPPLER_PATH is configured."
                    )
            except Exception:
                warnings.append(
                    "Could not verify Poppler/pdfinfo availability. Ensure Poppler is installed "
                    "or set AI_ML_POPPLER_PATH."
                )

        return errors, warnings

    def _check_model_artifacts(self) -> List[str]:
        warnings: List[str] = []

        artifact_paths = (
            ("AI_ML_AUTHENTICITY_MODEL_PATH", getattr(settings, "AI_ML_AUTHENTICITY_MODEL_PATH", "")),
            (
                "AI_ML_AUTHENTICITY_TORCH_MODEL_PATH",
                getattr(settings, "AI_ML_AUTHENTICITY_TORCH_MODEL_PATH", ""),
            ),
            ("AI_ML_FRAUD_MODEL_PATH", getattr(settings, "AI_ML_FRAUD_MODEL_PATH", "")),
            ("AI_ML_SIGNATURE_MODEL_PATH", getattr(settings, "AI_ML_SIGNATURE_MODEL_PATH", "")),
            ("AI_ML_RVL_CDIP_MODEL_PATH", getattr(settings, "AI_ML_RVL_CDIP_MODEL_PATH", "")),
            ("AI_ML_MIDV500_MODEL_PATH", getattr(settings, "AI_ML_MIDV500_MODEL_PATH", "")),
        )

        for setting_name, raw_path in artifact_paths:
            if not raw_path:
                warnings.append(
                    f"{setting_name} is not configured; runtime may fall back to heuristics."
                )
                continue
            path = self._resolve_path(raw_path)
            if not path.exists():
                warnings.append(
                    f"{setting_name} points to a missing file: {path}"
                )

        return warnings

    def _resolve_path(self, raw_path: str | Path) -> Path:
        path = Path(str(raw_path))
        if not path.is_absolute():
            path = Path(settings.BASE_DIR) / path
        return path

    def _load_report(self, setting_name: str, default_name: str) -> tuple[dict[str, Any] | None, Path, str | None]:
        raw_path = getattr(settings, setting_name, default_name)
        path = self._resolve_path(raw_path)
        if not path.exists():
            return None, path, f"{setting_name} not found at {path}"

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            return None, path, f"Failed to parse {path}: {exc}"

        if not isinstance(payload, dict):
            return None, path, f"{path} does not contain a JSON object."
        return payload, path, None

    def _check_metric(
        self,
        *,
        metric_name: str,
        metric_value: Any,
        threshold: float,
        gates_enabled: bool,
        errors: List[str],
        warnings: List[str],
    ) -> None:
        if metric_value is None:
            warnings.append(f"Metric `{metric_name}` is missing from report.")
            return

        try:
            value = float(metric_value)
        except (TypeError, ValueError):
            target = errors if gates_enabled else warnings
            target.append(
                f"Metric `{metric_name}` is non-numeric: {metric_value!r}."
            )
            return

        if value < threshold:
            message = (
                f"Metric `{metric_name}`={value:.4f} is below minimum "
                f"{threshold:.4f}."
            )
            if gates_enabled:
                errors.append(message)
            else:
                warnings.append(message)

    def _check_model_quality(self) -> Tuple[List[str], List[str]]:
        errors: List[str] = []
        warnings: List[str] = []

        gates_enabled = bool(getattr(settings, "AI_ML_METRIC_GATES_ENABLED", False))
        if not gates_enabled:
            warnings.append(
                "AI_ML_METRIC_GATES_ENABLED is disabled; strict quality gating is not enforced."
            )
        training_report, training_path, training_error = self._load_report(
            "AI_ML_TRAINING_REPORT_PATH",
            "models/training_report.json",
        )
        if training_error:
            if gates_enabled:
                errors.append(training_error)
            else:
                warnings.append(training_error)
        elif training_report is not None:
            self._check_metric(
                metric_name="authenticity_pytorch.val_f1",
                metric_value=(training_report.get("authenticity_pytorch") or {}).get("val_f1"),
                threshold=float(getattr(settings, "AI_ML_METRIC_MIN_AUTHENTICITY_F1", 0.70)),
                gates_enabled=gates_enabled,
                errors=errors,
                warnings=warnings,
            )
            self._check_metric(
                metric_name="authenticity_pytorch.val_accuracy",
                metric_value=(training_report.get("authenticity_pytorch") or {}).get("val_accuracy"),
                threshold=float(
                    getattr(settings, "AI_ML_METRIC_MIN_AUTHENTICITY_ACCURACY", 0.70)
                ),
                gates_enabled=gates_enabled,
                errors=errors,
                warnings=warnings,
            )
            self._check_metric(
                metric_name="signature.val_f1",
                metric_value=(training_report.get("signature") or {}).get("val_f1"),
                threshold=float(getattr(settings, "AI_ML_METRIC_MIN_SIGNATURE_F1", 0.70)),
                gates_enabled=gates_enabled,
                errors=errors,
                warnings=warnings,
            )
            self._check_metric(
                metric_name="signature.val_accuracy",
                metric_value=(training_report.get("signature") or {}).get("val_accuracy"),
                threshold=float(
                    getattr(settings, "AI_ML_METRIC_MIN_SIGNATURE_ACCURACY", 0.70)
                ),
                gates_enabled=gates_enabled,
                errors=errors,
                warnings=warnings,
            )

        classifier_report, classifier_path, classifier_error = self._load_report(
            "AI_ML_DOC_CLASSIFIER_REPORT_PATH",
            "models/document_classifier_training_report.json",
        )
        if classifier_error:
            if gates_enabled:
                errors.append(classifier_error)
            else:
                warnings.append(classifier_error)
        elif classifier_report is not None:
            self._check_metric(
                metric_name="rvl_cdip.metrics.macro_f1",
                metric_value=((classifier_report.get("rvl_cdip") or {}).get("metrics") or {}).get("macro_f1"),
                threshold=float(getattr(settings, "AI_ML_METRIC_MIN_RVL_CDIP_MACRO_F1", 0.60)),
                gates_enabled=gates_enabled,
                errors=errors,
                warnings=warnings,
            )
            self._check_metric(
                metric_name="midv500.metrics.macro_f1",
                metric_value=((classifier_report.get("midv500") or {}).get("metrics") or {}).get("macro_f1"),
                threshold=float(getattr(settings, "AI_ML_METRIC_MIN_MIDV500_MACRO_F1", 0.40)),
                gates_enabled=gates_enabled,
                errors=errors,
                warnings=warnings,
            )

        if gates_enabled and not errors and not warnings:
            # Gives a positive signal that production-quality checks are active.
            self.stdout.write(self.style.SUCCESS("Model quality gates are enabled and passed."))

        _ = training_path, classifier_path
        return errors, warnings