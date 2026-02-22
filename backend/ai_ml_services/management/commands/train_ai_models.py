"""Django management command entrypoint for AI/ML training pipeline."""

from ai_ml_services.commands.train_ai_models import Command

__all__ = ["Command"]
