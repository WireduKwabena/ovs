"""Django management command entrypoint for document type classifier training."""

from ai_ml_services.commands.train_document_classifiers import Command

__all__ = ["Command"]
