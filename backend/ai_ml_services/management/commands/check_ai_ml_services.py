"""Django management command entrypoint for AI/ML preflight checks."""

from ai_ml_services.commands.check_ai_ml_services import Command

__all__ = ["Command"]
