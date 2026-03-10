"""Lazy public exports for applications app models."""

__all__ = [
    "VettingCase",
    "Document",
    "VerificationResult",
    "ConsistencyCheck",
    "InterrogationFlag",
    "VerificationSource",
    "VerificationRequest",
    "ExternalVerificationResult",
]


def __getattr__(name):
    if name in __all__:
        from apps.applications import models

        return getattr(models, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
