"""Backward-compatible forgery generation exports.

Canonical implementation lives in ``ai_ml_services.datasets.generate_forgeries``.
"""

from ai_ml_services.datasets.generate_forgeries import ForgeryGenerator, generate_forgeries

__all__ = ["ForgeryGenerator", "generate_forgeries"]
