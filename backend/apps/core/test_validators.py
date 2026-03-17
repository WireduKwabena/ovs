"""Tests for apps.core.validators (JSONSchemaValidator)."""

from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.core.validators import (
    DETAILED_RESULTS_SCHEMA,
    EVIDENCE_SCHEMA,
    FRAUD_INDICATORS_SCHEMA,
    JSONSchemaValidator,
    SUGGESTED_QUESTIONS_SCHEMA,
    _validate_against_schema,
)


class ValidateAgainstSchemaFallbackTests(SimpleTestCase):
    """Tests for the fallback path when jsonschema is not installed."""

    def _without_jsonschema(self):
        return patch("builtins.__import__", side_effect=_block_jsonschema_import)

    def test_object_schema_accepts_dict(self):
        # No jsonschema - falls back to type check only.
        with patch.dict("sys.modules", {"jsonschema": None}):
            # Should not raise
            _validate_against_schema({"key": "value"}, {"type": "object"})

    def test_object_schema_rejects_list(self):
        with patch.dict("sys.modules", {"jsonschema": None}):
            with self.assertRaises(ValidationError):
                _validate_against_schema([], {"type": "object"})

    def test_array_schema_accepts_list(self):
        with patch.dict("sys.modules", {"jsonschema": None}):
            _validate_against_schema(["a", "b"], {"type": "array"})

    def test_array_schema_rejects_dict(self):
        with patch.dict("sys.modules", {"jsonschema": None}):
            with self.assertRaises(ValidationError):
                _validate_against_schema({}, {"type": "array"})


class JSONSchemaValidatorTests(SimpleTestCase):
    def test_evidence_schema_accepts_valid_dict(self):
        validator = JSONSchemaValidator(EVIDENCE_SCHEMA)
        # Should not raise
        validator({
            "authenticity_score": 92.0,
            "fraud_risk_score": 18.0,
            "fraud_prediction": "legitimate",
        })

    def test_evidence_schema_accepts_empty_dict(self):
        # Schema has no required fields
        validator = JSONSchemaValidator(EVIDENCE_SCHEMA)
        validator({})

    def test_fraud_indicators_schema_accepts_list_of_strings(self):
        validator = JSONSchemaValidator(FRAUD_INDICATORS_SCHEMA)
        validator(["placeholder_pipeline", "suspicious_filename"])

    def test_fraud_indicators_schema_accepts_empty_list(self):
        validator = JSONSchemaValidator(FRAUD_INDICATORS_SCHEMA)
        validator([])

    def test_suggested_questions_schema_accepts_valid_list(self):
        validator = JSONSchemaValidator(SUGGESTED_QUESTIONS_SCHEMA)
        validator(["Can you clarify the source?", "Any edits?"])

    def test_detailed_results_schema_accepts_valid_dict(self):
        validator = JSONSchemaValidator(DETAILED_RESULTS_SCHEMA)
        validator({"pipeline": "placeholder", "document_type": "passport"})

    def test_validator_is_callable(self):
        validator = JSONSchemaValidator(EVIDENCE_SCHEMA)
        self.assertTrue(callable(validator))

    def test_deconstruct_returns_expected_tuple(self):
        validator = JSONSchemaValidator(EVIDENCE_SCHEMA)
        path, args, kwargs = validator.deconstruct()
        self.assertIn("JSONSchemaValidator", path)
        self.assertEqual(args, [EVIDENCE_SCHEMA])
        self.assertEqual(kwargs, {})

    def test_fallback_rejects_wrong_type_for_object_schema(self):
        validator = JSONSchemaValidator({"type": "object"})
        with patch.dict("sys.modules", {"jsonschema": None}):
            with self.assertRaises(ValidationError):
                validator("not a dict")

    def test_fallback_rejects_wrong_type_for_array_schema(self):
        validator = JSONSchemaValidator({"type": "array"})
        with patch.dict("sys.modules", {"jsonschema": None}):
            with self.assertRaises(ValidationError):
                validator({"not": "a list"})
