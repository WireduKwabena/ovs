"""Signature authenticity services.

Optional CV dependencies are loaded lazily so package import remains safe in
environments that do not install heavy ML extras.
"""

__all__ = ["SignatureAuthenticityDetector", "train_signature_model"]


def __getattr__(name):
    if name == "SignatureAuthenticityDetector":
        from ai_ml_services.signature.signature_detector import SignatureAuthenticityDetector

        return SignatureAuthenticityDetector
    if name == "train_signature_model":
        from ai_ml_services.signature.train import train_signature_model

        return train_signature_model
    raise AttributeError(name)
