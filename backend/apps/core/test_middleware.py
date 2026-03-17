"""Tests for apps.core.middleware (RequestIDMiddleware)."""

from unittest.mock import MagicMock

from django.test import SimpleTestCase, RequestFactory, override_settings

from apps.core.middleware import (
    RequestIDMiddleware,
    _is_valid_request_id,
    get_current_request_id,
    set_current_request_id,
    REQUEST_ID_ATTR,
    REQUEST_ID_HEADER,
    REQUEST_ID_META_KEY,
)


class IsValidRequestIdTests(SimpleTestCase):
    def test_empty_string_is_invalid(self):
        self.assertFalse(_is_valid_request_id(""))

    def test_whitespace_is_invalid(self):
        self.assertFalse(_is_valid_request_id("   "))

    def test_normal_uuid_is_valid(self):
        self.assertTrue(_is_valid_request_id("550e8400-e29b-41d4-a716-446655440000"))

    def test_string_at_max_length_is_valid(self):
        self.assertTrue(_is_valid_request_id("x" * 128))

    def test_string_over_max_length_is_invalid(self):
        self.assertFalse(_is_valid_request_id("x" * 129))


class ContextVarTests(SimpleTestCase):
    def test_get_current_request_id_returns_empty_by_default(self):
        set_current_request_id("")
        self.assertEqual(get_current_request_id(), "")

    def test_set_and_get_request_id(self):
        set_current_request_id("abc-123")
        self.assertEqual(get_current_request_id(), "abc-123")
        # Clean up
        set_current_request_id("")


class RequestIDMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.get_response = MagicMock(return_value=MagicMock(status_code=200))
        self.middleware = RequestIDMiddleware(self.get_response)

    def _make_request(self, incoming_id=None):
        request = self.factory.get("/")
        if incoming_id:
            request.META[REQUEST_ID_META_KEY] = incoming_id
        return request

    def test_generates_uuid_when_no_header(self):
        request = self._make_request()
        self.middleware(request)
        request_id = getattr(request, REQUEST_ID_ATTR, None)
        self.assertIsNotNone(request_id)
        self.assertGreater(len(request_id), 0)

    def test_uses_incoming_header_when_valid(self):
        incoming = "my-upstream-trace-id"
        request = self._make_request(incoming_id=incoming)
        self.middleware(request)
        self.assertEqual(getattr(request, REQUEST_ID_ATTR), incoming)

    def test_generates_new_id_when_incoming_too_long(self):
        too_long = "x" * 200
        request = self._make_request(incoming_id=too_long)
        self.middleware(request)
        assigned = getattr(request, REQUEST_ID_ATTR)
        self.assertNotEqual(assigned, too_long)
        self.assertLessEqual(len(assigned), 128)

    def test_response_has_request_id_header(self):
        request = self._make_request()
        response = MagicMock()
        self.get_response.return_value = response
        self.middleware(request)
        request_id = getattr(request, REQUEST_ID_ATTR)
        response.__setitem__.assert_called_with(REQUEST_ID_HEADER, request_id)

    def test_different_requests_get_different_ids(self):
        req1 = self._make_request()
        req2 = self._make_request()
        self.middleware(req1)
        self.middleware(req2)
        id1 = getattr(req1, REQUEST_ID_ATTR)
        id2 = getattr(req2, REQUEST_ID_ATTR)
        self.assertNotEqual(id1, id2)

    def test_context_var_is_set_during_request(self):
        captured = {}

        def capturing_get_response(request):
            captured["id"] = get_current_request_id()
            return MagicMock()

        middleware = RequestIDMiddleware(capturing_get_response)
        request = self._make_request(incoming_id="trace-xyz")
        middleware(request)
        self.assertEqual(captured["id"], "trace-xyz")
