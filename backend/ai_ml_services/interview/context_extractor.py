"""Compatibility wrapper for interview context extraction.

The canonical implementation lives in ``apps.interviews.context_extractor``.
This module is kept to avoid breaking legacy imports from the AI service layer.
"""

from apps.interviews.context_extractor import ApplicantContextExtractor

__all__ = ["ApplicantContextExtractor"]
