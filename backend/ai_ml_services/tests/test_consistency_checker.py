"""Tests for authenticity consistency checker hardening."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from django.utils import timezone

from ai_ml_services.authenticity.consistency_checker import ConsistencyChecker


class TestConsistencyChecker(SimpleTestCase):
    @patch("ai_ml_services.authenticity.consistency_checker.spacy.blank")
    @patch("ai_ml_services.authenticity.consistency_checker.spacy.load")
    def test_init_falls_back_to_blank_model_when_spacy_models_missing(
        self,
        mock_load,
        mock_blank,
    ):
        mock_load.side_effect = OSError("model not found")
        blank_model = MagicMock()
        blank_model.pipe_names = []
        mock_blank.return_value = blank_model

        checker = ConsistencyChecker()

        self.assertIs(checker.nlp, blank_model)
        self.assertTrue(checker.spacy_model_name.startswith("blank:"))
        self.assertFalse(checker.entity_extraction_available)
        self.assertGreaterEqual(mock_load.call_count, 2)

    def test_parse_date_returns_timezone_aware_datetime(self):
        checker = ConsistencyChecker.__new__(ConsistencyChecker)

        parsed = checker._parse_date("2024-10-01")

        self.assertIsNotNone(parsed)
        self.assertFalse(timezone.is_naive(parsed))

    def test_check_date_consistency_handles_mixed_naive_and_aware_inputs(self):
        checker = ConsistencyChecker.__new__(ConsistencyChecker)
        checker.extract_entities = MagicMock(return_value={"dates": []})

        documents = [
            {
                "text": "",
                "document_type": "id_card",
                "extracted_data": {
                    "date_of_birth": "1990-01-01",
                    "date_issued": "2020-01-01T00:00:00+00:00",
                },
            }
        ]

        result = checker.check_date_consistency(documents)

        self.assertIn("consistent", result)
        self.assertIn("confidence", result)
        self.assertIn("inconsistencies", result)
