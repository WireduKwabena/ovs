from __future__ import annotations

import importlib
from importlib import metadata as importlib_metadata
import json
import re
import shutil
import subprocess
import sys
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
        syntax_errors = self._check_syntax(ai_ml_dir)
        if syntax_errors:
            for message in syntax_errors:
                self.stdout.write(self.style.ERROR(f"ERROR: {message}"))
            raise CommandError(
                f"Python syntax validation failed for ai_ml_services "
                f"({len(syntax_errors)} file(s))."
            )

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

        self.stdout.write("Checking dependency compatibility...")
        dependency_errors, dependency_warnings = self._check_dependency_compatibility()
        errors.extend(dependency_errors)
        warnings.extend(dependency_warnings)

        self.stdout.write("Checking model artifact paths...")
        warnings.extend(self._check_model_artifacts())

        self.stdout.write("Checking model manifest...")
        manifest_errors, manifest_warnings = self._check_model_manifest()
        errors.extend(manifest_errors)
        warnings.extend(manifest_warnings)

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

    def _check_syntax(self, base_dir: Path) -> List[str]:
        errors: List[str] = []
        for py_file in base_dir.rglob("*.py"):
            if "__pycache__" in py_file.parts:
                continue
            try:
                source = py_file.read_text(encoding="utf-8")
                compile(source, str(py_file), "exec")
            except Exception as exc:
                errors.append(f"{py_file}: {exc}")
        return errors

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
        import_timeout_seconds = int(
            getattr(settings, "AI_ML_PREFLIGHT_IMPORT_TIMEOUT_SECONDS", 20)
        )
        errors: List[str] = []
        for module in required_modules:
            try:
                script = (
                    "import importlib\n"
                    f"importlib.import_module({module!r})\n"
                )
                result = subprocess.run(
                    [sys.executable, "-c", script],
                    capture_output=True,
                    text=True,
                    timeout=max(1, import_timeout_seconds),
                    check=False,
                )
                if result.returncode != 0:
                    stderr = (result.stderr or "").strip()
                    stdout = (result.stdout or "").strip()
                    detail = stderr or stdout or f"exit_code={result.returncode}"
                    errors.append(f"Could not import `{module}`: {detail}")
            except subprocess.TimeoutExpired:
                errors.append(
                    f"Could not import `{module}`: import timed out after "
                    f"{import_timeout_seconds}s."
                )
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

        retention_setting_names = (
            "PII_RETENTION_DAYS",
            "BIOMETRIC_RETENTION_DAYS",
            "BACKGROUND_CHECK_RETENTION_DAYS",
            "AUDIT_LOG_RETENTION_DAYS",
        )
        for setting_name in retention_setting_names:
            raw_value = getattr(settings, setting_name, None)
            try:
                days = int(raw_value)
            except (TypeError, ValueError):
                errors.append(f"{setting_name} must be an integer day count.")
                continue

            if days < 1:
                errors.append(f"{setting_name} must be >= 1 day.")
            elif days > 3650:
                warnings.append(
                    f"{setting_name} is unusually large ({days} days). "
                    "Confirm this aligns with your data governance policy."
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

    def _normalized_version_tuple(self, raw_version: str) -> tuple[int, int, int]:
        parts = [int(match) for match in re.findall(r"\d+", str(raw_version))]
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])

    def _package_version(self, package_name: str) -> str | None:
        try:
            return importlib_metadata.version(package_name)
        except importlib_metadata.PackageNotFoundError:
            return None

    def _check_dependency_compatibility(self) -> Tuple[List[str], List[str]]:
        errors: List[str] = []
        warnings: List[str] = []

        numpy_version = self._package_version("numpy")
        if not numpy_version:
            return errors, warnings

        numpy_tuple = self._normalized_version_tuple(numpy_version)
        opencv_packages = (
            "opencv-python",
            "opencv-python-headless",
            "opencv-contrib-python",
        )
        for package_name in opencv_packages:
            package_version = self._package_version(package_name)
            if not package_version:
                continue

            package_tuple = self._normalized_version_tuple(package_version)
            if package_tuple >= (4, 13, 0) and numpy_tuple < (2, 0, 0):
                warnings.append(
                    f"{package_name}=={package_version} typically expects numpy>=2.0, "
                    f"but numpy=={numpy_version} is installed. Pin compatible versions "
                    "or update your constraints lock."
                )

        return errors, warnings

    def _check_model_manifest(self) -> Tuple[List[str], List[str]]:
        errors: List[str] = []
        warnings: List[str] = []

        required = bool(getattr(settings, "AI_ML_MODEL_MANIFEST_REQUIRED", False))
        manifest_setting = getattr(settings, "AI_ML_MODEL_MANIFEST_PATH", "")
        manifest_path = self._resolve_path(manifest_setting or "models/model_manifest.json")

        if not manifest_path.exists():
            message = f"AI_ML_MODEL_MANIFEST_PATH not found at {manifest_path}"
            if required:
                errors.append(message)
            else:
                warnings.append(message)
            return errors, warnings

        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            message = f"Failed to parse model manifest {manifest_path}: {exc}"
            if required:
                errors.append(message)
            else:
                warnings.append(message)
            return errors, warnings

        if not isinstance(payload, dict):
            message = f"Model manifest must be a JSON object: {manifest_path}"
            if required:
                errors.append(message)
            else:
                warnings.append(message)
            return errors, warnings

        models_payload = payload.get("models")
        if not isinstance(models_payload, (dict, list)):
            message = (
                f"Model manifest must include a `models` mapping/list: {manifest_path}"
            )
            if required:
                errors.append(message)
            else:
                warnings.append(message)
            return errors, warnings

        if isinstance(models_payload, dict):
            model_entries = list(models_payload.values())
        else:
            model_entries = list(models_payload)

        manifest_paths: set[Path] = set()
        target_for_entry_issues = errors if required else warnings
        for entry in model_entries:
            if not isinstance(entry, dict):
                target_for_entry_issues.append(
                    f"Invalid model entry in manifest (expected object): {entry!r}"
                )
                continue

            entry_path_raw = entry.get("path")
            entry_version = str(entry.get("version", "") or "").strip()
            entry_sha256 = str(entry.get("sha256", "") or "").strip()
            entry_trained_at = str(entry.get("trained_at", "") or "").strip()

            if not entry_path_raw:
                target_for_entry_issues.append("Model manifest entry is missing `path`.")
                continue
            try:
                entry_path = self._resolve_path(entry_path_raw).resolve()
            except Exception:
                entry_path = Path(str(entry_path_raw))
            manifest_paths.add(entry_path)

            if not entry_version:
                target_for_entry_issues.append(
                    f"Model manifest entry missing `version`: {entry_path_raw}"
                )
            if not re.fullmatch(r"[0-9a-fA-F]{64}", entry_sha256):
                target_for_entry_issues.append(
                    f"Model manifest entry has invalid/missing sha256: {entry_path_raw}"
                )
            if not entry_trained_at:
                target_for_entry_issues.append(
                    f"Model manifest entry missing `trained_at`: {entry_path_raw}"
                )

        artifact_setting_names = (
            "AI_ML_AUTHENTICITY_MODEL_PATH",
            "AI_ML_AUTHENTICITY_TORCH_MODEL_PATH",
            "AI_ML_FRAUD_MODEL_PATH",
            "AI_ML_SIGNATURE_MODEL_PATH",
            "AI_ML_RVL_CDIP_MODEL_PATH",
            "AI_ML_MIDV500_MODEL_PATH",
        )
        target_for_coverage_issues = errors if required else warnings
        for setting_name in artifact_setting_names:
            raw_value = getattr(settings, setting_name, "")
            if not raw_value:
                continue
            resolved_path = self._resolve_path(raw_value)
            if not resolved_path.exists():
                continue
            try:
                normalized = resolved_path.resolve()
            except Exception:
                normalized = resolved_path

            if normalized not in manifest_paths:
                target_for_coverage_issues.append(
                    f"{setting_name} points to {resolved_path}, but this model path is "
                    "missing from AI_ML_MODEL_MANIFEST_PATH."
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
