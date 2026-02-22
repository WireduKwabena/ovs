"""Validation utilities for uploaded files."""

import mimetypes
import logging
from typing import List, Optional

from rest_framework.exceptions import ValidationError

logger = logging.getLogger(__name__)

try:
    import magic
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    magic = None


def _sniff_mime_from_header(file_content: bytes, filename: str) -> str:
    header = file_content[:12]
    if header.startswith(b"%PDF"):
        return "application/pdf"
    if header.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


def validate_file_type(file_content: bytes, filename: str, allowed_types: Optional[List[str]] = None):
    """Validate file type using magic numbers"""
    if allowed_types is None:
        allowed_types = ['application/pdf', 'image/jpeg', 'image/png']

    try:
        if magic is not None:
            file_type = magic.from_buffer(file_content[:1024], mime=True)
        else:
            file_type = _sniff_mime_from_header(file_content, filename)
    except Exception as e:
        logger.error(f"Error determining file type for {filename}: {e}", exc_info=True)
        raise ValidationError(f'Could not determine file type for {filename}')

    if file_type not in allowed_types:
        logger.warning(f"File {filename} has unsupported type: {file_type}. Allowed types: {allowed_types}")
        raise ValidationError(
            f'Unsupported file type: {file_type}. Allowed types are: {", ".join(allowed_types)}'
        )

    logger.info(f"File {filename} validated as type: {file_type}")
    return True


def validate_file_size(file_size: int, max_size: int = 10485760):
    """Limit file size to 10MB"""
    if file_size > max_size:
        logger.warning(f"File size {file_size} bytes exceeds limit of {max_size} bytes.")
        raise ValidationError(f'File size exceeds {max_size / (1024 * 1024):.0f}MB limit')

    logger.info(f"File size {file_size} bytes is within limit.")
    return True
