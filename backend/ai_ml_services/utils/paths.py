"""Cross-platform path resolution helpers for settings-driven file paths."""

from __future__ import annotations

import re
from pathlib import Path, PureWindowsPath


_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")


def resolve_settings_path(
    raw_path: str | Path,
    *,
    base_dir: Path,
    fallback_dir: Path | None = None,
) -> Path:
    """
    Resolve a path from settings safely across Windows and POSIX runtimes.

    Why this exists:
    - Windows absolute paths like ``A:\\repo\\backend\\models\\x.pkl`` are not
      considered absolute on Linux and can be accidentally prefixed with
      ``base_dir``.
    - In containerized runtime we prefer deterministic fallback to the model
      directory basename when stale host-specific absolute paths are provided.
    """
    text = str(raw_path or "").strip()
    if not text:
        return Path(base_dir)

    base_dir = Path(base_dir)
    fallback_dir = Path(fallback_dir) if fallback_dir is not None else None

    native_path = Path(text)
    if native_path.is_absolute():
        return native_path

    normalized = text.replace("\\", "/")
    lowered = normalized.lower()

    if lowered.startswith("backend/"):
        return base_dir / Path(normalized[len("backend/") :])

    marker = "/backend/"
    marker_index = lowered.find(marker)
    if marker_index >= 0:
        return base_dir / Path(normalized[marker_index + len(marker) :])

    if _WINDOWS_ABSOLUTE_PATH_RE.match(text):
        win_name = PureWindowsPath(text).name
        target_root = fallback_dir or base_dir
        return target_root / win_name

    return base_dir / native_path
