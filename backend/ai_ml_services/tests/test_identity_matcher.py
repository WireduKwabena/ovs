"""Tests for document-vs-interview identity matching helpers."""

from __future__ import annotations

import numpy as np
from django.test import SimpleTestCase
from unittest.mock import patch

from ai_ml_services.video.identity_matcher import IdentityMatcher


class IdentityMatcherTests(SimpleTestCase):
    def test_match_returns_backend_error_when_unavailable(self):
        matcher = IdentityMatcher()
        matcher.backend = "unavailable"
        result = matcher.match_document_to_interview(
            document_path="unused-document.jpg",
            interview_video_path="unused-video.mp4",
        )
        self.assertFalse(result["success"])
        self.assertIn("No embedding backend available", result["error"])

    def test_match_success_payload_with_patched_steps(self):
        matcher = IdentityMatcher()
        matcher.backend = "facenet"
        matcher.requested_backend = "auto"
        matcher.similarity_threshold = 0.70

        document_image = np.zeros((120, 120, 3), dtype=np.uint8)
        document_face = np.ones((64, 64, 3), dtype=np.uint8)
        interview_face = np.full((64, 64, 3), 2, dtype=np.uint8)

        with patch.object(
            matcher,
            "_read_document_image",
            return_value=document_image,
        ), patch.object(
            matcher,
            "_crop_face",
            return_value=(document_face, (10, 10, 64, 64)),
        ), patch.object(
            matcher,
            "_extract_interview_face",
            return_value=(interview_face, (8, 8, 64, 64)),
        ), patch.object(
            matcher,
            "_extract_embedding",
            side_effect=[
                np.array([1.0, 0.0], dtype=np.float32),
                np.array([1.0, 0.0], dtype=np.float32),
            ],
        ):
            result = matcher.match_document_to_interview(
                document_path="id-card.jpg",
                interview_video_path="candidate-video.mp4",
            )

        self.assertTrue(result["success"])
        self.assertTrue(result["document_face_detected"])
        self.assertTrue(result["interview_face_detected"])
        self.assertTrue(result["is_match"])
        self.assertGreaterEqual(result["similarity_score"], 0.9)

    def test_match_handles_missing_document_face(self):
        matcher = IdentityMatcher()
        matcher.backend = "facenet"

        with patch.object(
            matcher,
            "_read_document_image",
            return_value=np.zeros((100, 100, 3), dtype=np.uint8),
        ), patch.object(
            matcher,
            "_crop_face",
            return_value=(None, None),
        ):
            result = matcher.match_document_to_interview(
                document_path="id-card.jpg",
                interview_video_path="candidate-video.mp4",
            )

        self.assertFalse(result["success"])
        self.assertIn("No face detected in the provided document", result["error"])
