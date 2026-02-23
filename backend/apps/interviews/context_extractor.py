"""Compatibility wrapper for interview context extraction.

The canonical implementation now lives in ``ai_ml_services.interview.context_extractor``.
This module is kept to avoid breaking legacy imports from the Django app layer.
"""

from ai_ml_services.interview.context_extractor import ApplicantContextExtractor

__all__ = ["ApplicantContextExtractor"]
