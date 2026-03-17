"""
Core JSON schema validators for model JSONField validation.

Usage in serializers:
    from apps.core.validators import JSONSchemaValidator, EVIDENCE_SCHEMA

    class MySerializer(serializers.Serializer):
        evidence = serializers.JSONField(
            validators=[JSONSchemaValidator(EVIDENCE_SCHEMA)]
        )
"""

from __future__ import annotations

import logging
from typing import Any

from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schemas for critical JSONField structures
# ---------------------------------------------------------------------------

#: Evidence dict stored on InterrogationFlag.evidence
EVIDENCE_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "authenticity_score": {"type": "number"},
        "fraud_risk_score": {"type": "number"},
        "fraud_prediction": {"type": "string"},
    },
}

#: fraud_indicators list stored on VerificationResult
FRAUD_INDICATORS_SCHEMA: dict = {
    "type": "array",
    "items": {"type": "string"},
}

#: detailed_results dict stored on VerificationResult
DETAILED_RESULTS_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "pipeline": {"type": "string"},
        "document_type": {"type": "string"},
    },
}

#: suggested_questions list stored on InterrogationFlag
SUGGESTED_QUESTIONS_SCHEMA: dict = {
    "type": "array",
    "items": {"type": "string"},
    "maxItems": 20,
}


# ---------------------------------------------------------------------------
# Validator implementation
# ---------------------------------------------------------------------------

def _validate_against_schema(value: Any, schema: dict) -> None:
    """
    Validate ``value`` against ``schema`` using jsonschema if available,
    falling back to basic type checks if the library is not installed.
    """
    try:
        import jsonschema  # optional dependency
        try:
            jsonschema.validate(value, schema)
        except jsonschema.ValidationError as exc:
            raise ValidationError(f"JSON schema validation failed: {exc.message}") from exc
        except jsonschema.SchemaError as exc:
            logger.error("Invalid JSON schema definition: %s", exc, exc_info=True)
    except ImportError:
        # jsonschema not installed — apply only top-level type check.
        expected_type = schema.get("type")
        if expected_type == "object" and not isinstance(value, dict):
            raise ValidationError(f"Expected a JSON object (dict), got {type(value).__name__}.")
        if expected_type == "array" and not isinstance(value, list):
            raise ValidationError(f"Expected a JSON array (list), got {type(value).__name__}.")


class JSONSchemaValidator:
    """Django-compatible callable validator for JSONField."""

    def __init__(self, schema: dict):
        self.schema = schema

    def __call__(self, value: Any) -> None:
        _validate_against_schema(value, self.schema)

    def deconstruct(self):
        return (
            f"{self.__class__.__module__}.{self.__class__.__qualname__}",
            [self.schema],
            {},
        )
