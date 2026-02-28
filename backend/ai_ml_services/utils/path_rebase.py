"""Helpers for rebasing absolute dataset paths after project relocation."""

from __future__ import annotations

from pathlib import Path


def infer_backend_root(reference_path: Path) -> Path:
    """Infer backend root from a path near the project tree."""
    resolved = Path(reference_path)
    for candidate in (resolved, *resolved.parents):
        if candidate.name.lower() == "backend":
            return candidate

    cwd = Path.cwd()
    for candidate in (cwd, *cwd.parents):
        if candidate.name.lower() == "backend":
            return candidate

    return cwd


def rebase_moved_backend_path(raw_path: str | Path, backend_root: Path) -> Path:
    """Map stale absolute paths containing `/backend/` to current backend root."""
    path = Path(str(raw_path))
    if path.exists():
        return path

    normalized = str(raw_path).replace("\\", "/")
    lowered = normalized.lower()

    marker = "/backend/"
    marker_index = lowered.find(marker)
    if marker_index >= 0:
        suffix = normalized[marker_index + len(marker) :]
    elif lowered.startswith("backend/"):
        suffix = normalized[len("backend/") :]
    else:
        return path

    candidate = backend_root / Path(suffix)
    return candidate if candidate.exists() else path
