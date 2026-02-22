"""PDF utility helpers for consistent pdf2image behavior across environments."""

from __future__ import annotations

import logging
import os
import shutil
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

from django.conf import settings

logger = logging.getLogger(__name__)


def _as_existing_dir(path_value: str) -> Optional[Path]:
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = Path(settings.BASE_DIR) / path
    if path.is_file():
        path = path.parent
    return path if path.exists() and path.is_dir() else None


@lru_cache(maxsize=1)
def resolve_poppler_path() -> Optional[str]:
    """Resolve a usable Poppler `bin` directory for pdf2image."""
    configured = (
        str(getattr(settings, "AI_ML_POPPLER_PATH", "") or "").strip()
        or str(os.getenv("AI_ML_POPPLER_PATH", "")).strip()
        or str(os.getenv("POPPLER_PATH", "")).strip()
    )
    if configured:
        configured_dir = _as_existing_dir(configured)
        if configured_dir:
            return str(configured_dir)
        logger.warning("Configured Poppler path is invalid: %s", configured)

    if shutil.which("pdfinfo"):
        return None

    local_app_data = os.getenv("LOCALAPPDATA")
    if not local_app_data:
        return None

    winget_root = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
    if not winget_root.exists():
        return None

    candidates = sorted(
        winget_root.glob(
            "oschwartz10612.Poppler_*/poppler-*/Library/bin/pdfinfo.exe"
        ),
        key=lambda candidate: candidate.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return None

    return str(candidates[0].parent)


def pdf2image_kwargs() -> Dict[str, str]:
    """Return optional kwargs for `pdf2image.convert_from_path`."""
    poppler_path = resolve_poppler_path()
    if not poppler_path:
        return {}
    return {"poppler_path": poppler_path}
