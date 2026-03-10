"""Document type classification utilities.

Optional ML dependencies (e.g., OpenCV) may be unavailable in lightweight test
environments, so imports are resolved lazily.
"""

__all__ = ["DocumentTypeClassifier", "DocumentFeatureExtractor"]


def __getattr__(name):
    if name == "DocumentTypeClassifier":
        from ai_ml_services.document_classification.classifier import DocumentTypeClassifier

        return DocumentTypeClassifier
    if name == "DocumentFeatureExtractor":
        from ai_ml_services.document_classification.features import DocumentFeatureExtractor

        return DocumentFeatureExtractor
    raise AttributeError(name)
