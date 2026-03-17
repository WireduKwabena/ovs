"""Tests for apps.core.exceptions (custom_exception_handler)."""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.exceptions import ValidationError, NotFound, PermissionDenied
from rest_framework.response import Response

from apps.core.exceptions import custom_exception_handler


def _make_context(view_name="MyView", method="GET", path="/api/test/"):
    view = MagicMock()
    view.__class__.__name__ = view_name
    request = MagicMock()
    request.method = method
    inner = MagicMock()
    inner.path = path
    request._request = inner
    return {"view": view, "request": request}


class CustomExceptionHandlerTests(SimpleTestCase):
    def test_returns_response_for_drf_validation_error(self):
        exc = ValidationError("bad input")
        context = _make_context()
        response = custom_exception_handler(exc, context)
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_returns_response_for_not_found(self):
        exc = NotFound("missing resource")
        context = _make_context()
        response = custom_exception_handler(exc, context)
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_returns_none_for_unhandled_exception(self):
        exc = RuntimeError("unexpected crash")
        context = _make_context()
        response = custom_exception_handler(exc, context)
        self.assertIsNone(response)

    def test_logs_warning_for_4xx_errors(self):
        exc = PermissionDenied("forbidden")
        context = _make_context()
        with patch("apps.core.exceptions.logger") as mock_logger:
            custom_exception_handler(exc, context)
        mock_logger.warning.assert_called_once()
        args = mock_logger.warning.call_args[0]
        self.assertIn("403", str(args))

    def test_logs_error_for_unhandled_exceptions(self):
        exc = RuntimeError("boom")
        context = _make_context()
        with patch("apps.core.exceptions.logger") as mock_logger:
            custom_exception_handler(exc, context)
        mock_logger.error.assert_called_once()

    def test_works_with_missing_view_in_context(self):
        exc = ValidationError("bad")
        context = {"view": None, "request": MagicMock()}
        response = custom_exception_handler(exc, context)
        self.assertIsNotNone(response)

    def test_works_with_empty_context(self):
        exc = ValidationError("bad")
        response = custom_exception_handler(exc, {})
        self.assertIsNotNone(response)
