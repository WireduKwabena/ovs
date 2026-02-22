"""Lazy public exports for rubrics app models."""

__all__ = ["VettingRubric", "RubricCriteria", "RubricEvaluation"]


def __getattr__(name):
    if name in __all__:
        from apps.rubrics import models

        return getattr(models, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
