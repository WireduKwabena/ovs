from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ai_ml_services.utils.paths import resolve_settings_path

DEFAULT_PLACEHOLDER_SHA256 = "0" * 64


@dataclass(frozen=True)
class ManifestArtifactTarget:
    name: str
    setting_name: str


ARTIFACT_TARGETS: tuple[ManifestArtifactTarget, ...] = (
    ManifestArtifactTarget("authenticity_tensorflow", "AI_ML_AUTHENTICITY_MODEL_PATH"),
    ManifestArtifactTarget("authenticity_pytorch", "AI_ML_AUTHENTICITY_TORCH_MODEL_PATH"),
    ManifestArtifactTarget("fraud_classifier", "AI_ML_FRAUD_MODEL_PATH"),
    ManifestArtifactTarget("signature_classifier", "AI_ML_SIGNATURE_MODEL_PATH"),
    ManifestArtifactTarget("rvl_cdip_classifier", "AI_ML_RVL_CDIP_MODEL_PATH"),
    ManifestArtifactTarget("midv500_classifier", "AI_ML_MIDV500_MODEL_PATH"),
)


class Command(BaseCommand):
    help = "Generate model manifest metadata (sha256/version/trained_at) for AI artifacts."
    requires_system_checks: list[str] = []

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default=getattr(settings, "AI_ML_MODEL_MANIFEST_PATH", "models/model_manifest.json"),
            help="Output manifest path (default: AI_ML_MODEL_MANIFEST_PATH).",
        )
        parser.add_argument(
            "--model-version",
            default="",
            help="Optional fixed version string for all manifest entries.",
        )
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Fail if any configured model path is missing.",
        )
        parser.add_argument(
            "--include-missing",
            action="store_true",
            help=(
                "Include configured-but-missing paths in manifest with placeholder checksum. "
                "Useful for inventory output."
            ),
        )

    def handle(self, *args, **options):
        output_path = self._resolve_path(str(options["output"]))
        fixed_version = str(options.get("model_version", "") or "").strip()
        strict = bool(options.get("strict"))
        include_missing = bool(options.get("include_missing"))

        generated_at = self._utc_now_iso()
        manifest_models: list[dict[str, object]] = []
        missing_paths: list[str] = []

        for target in ARTIFACT_TARGETS:
            raw_value = str(getattr(settings, target.setting_name, "") or "").strip()
            if not raw_value:
                continue

            resolved_path = self._resolve_path(raw_value)
            if not resolved_path.exists():
                message = (
                    f"{target.setting_name} points to a missing file: {resolved_path}"
                )
                missing_paths.append(message)
                self.stdout.write(self.style.WARNING(f"WARNING: {message}"))
                if include_missing:
                    manifest_models.append(
                        self._build_missing_entry(
                            name=target.name,
                            setting_name=target.setting_name,
                            path=resolved_path,
                            generated_at=generated_at,
                            fixed_version=fixed_version,
                        )
                    )
                continue

            manifest_models.append(
                self._build_entry(
                    name=target.name,
                    setting_name=target.setting_name,
                    path=resolved_path,
                    fixed_version=fixed_version,
                )
            )

        if strict and missing_paths:
            raise CommandError(
                "Model manifest generation failed due to missing artifacts in strict mode."
            )

        if not manifest_models:
            raise CommandError(
                "No model entries were generated. Verify AI_ML_*_MODEL_PATH settings."
            )

        payload = {
            "schema_version": 1,
            "generated_at": generated_at,
            "generated_by": "manage.py generate_model_manifest",
            "models": manifest_models,
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        self.stdout.write(
            self.style.SUCCESS(
                f"Wrote model manifest with {len(manifest_models)} entries to {output_path}"
            )
        )

    def _build_entry(
        self,
        *,
        name: str,
        setting_name: str,
        path: Path,
        fixed_version: str,
    ) -> dict[str, object]:
        trained_at = self._mtime_iso(path)
        version = fixed_version or f"artifact-{self._mtime_slug(path)}"
        return {
            "name": name,
            "setting": setting_name,
            "path": self._display_path(path),
            "version": version,
            "sha256": self._sha256(path),
            "trained_at": trained_at,
            "size_bytes": int(path.stat().st_size),
        }

    def _build_missing_entry(
        self,
        *,
        name: str,
        setting_name: str,
        path: Path,
        generated_at: str,
        fixed_version: str,
    ) -> dict[str, object]:
        return {
            "name": name,
            "setting": setting_name,
            "path": self._display_path(path),
            "version": fixed_version or "missing-artifact",
            "sha256": DEFAULT_PLACEHOLDER_SHA256,
            "trained_at": generated_at,
            "size_bytes": 0,
            "exists": False,
        }

    def _resolve_path(self, raw_path: str | Path) -> Path:
        return resolve_settings_path(
            raw_path,
            base_dir=Path(settings.BASE_DIR),
            fallback_dir=Path(getattr(settings, "MODEL_PATH", Path(settings.BASE_DIR) / "models")),
        )

    def _display_path(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(Path(settings.BASE_DIR).resolve()).as_posix()
        except Exception:
            return str(path)

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _mtime_iso(path: Path) -> str:
        value = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        return value.isoformat().replace("+00:00", "Z")

    @staticmethod
    def _mtime_slug(path: Path) -> str:
        value = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        return value.strftime("%Y%m%dT%H%M%SZ")

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")
