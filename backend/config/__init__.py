"""Config package exports.

Keep Celery import lazy so Django settings import does not pay Celery startup cost.
"""

from __future__ import annotations

from typing import Any

__all__ = ("celery_app",)


def __getattr__(name: str) -> Any:
    if name != "celery_app":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from .celery import app as celery_app

    return celery_app
