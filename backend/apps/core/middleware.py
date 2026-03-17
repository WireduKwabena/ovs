"""
Core middleware for request ID tracking and distributed tracing.
"""

import logging
import uuid

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_META_KEY = "HTTP_X_REQUEST_ID"
REQUEST_ID_ATTR = "_request_id"

# Thread-local / contextvars storage so Celery tasks can read the current ID.
try:
    from contextvars import ContextVar
    _current_request_id: ContextVar[str] = ContextVar("request_id", default="")
except ImportError:  # pragma: no cover - Python < 3.7
    _current_request_id = None  # type: ignore[assignment]


def get_current_request_id() -> str:
    """Return the request ID bound to the current execution context."""
    if _current_request_id is not None:
        return _current_request_id.get()
    return ""


def set_current_request_id(request_id: str) -> None:
    if _current_request_id is not None:
        _current_request_id.set(request_id)


class RequestIDMiddleware:
    """
    Attach a unique request ID to every inbound request.

    - Reads ``X-Request-ID`` from the incoming request headers (so upstream
      load balancers / API gateways can inject a correlation ID).
    - Generates a new UUID4 if no header is present.
    - Stores the ID on the request object as ``request._request_id`` and in
      the ``ContextVar`` so Celery tasks dispatched during the request can
      inherit it via ``apply_async(headers=...)``.
    - Echoes the ID back in the ``X-Request-ID`` response header.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.META.get(REQUEST_ID_META_KEY, "").strip()
        request_id = incoming if _is_valid_request_id(incoming) else str(uuid.uuid4())

        setattr(request, REQUEST_ID_ATTR, request_id)
        set_current_request_id(request_id)

        response = self.get_response(request)
        response[REQUEST_ID_HEADER] = request_id
        return response


def _is_valid_request_id(value: str) -> bool:
    """Accept non-empty, reasonably sized strings as incoming IDs."""
    stripped = value.strip()
    return bool(stripped) and len(stripped) <= 128
