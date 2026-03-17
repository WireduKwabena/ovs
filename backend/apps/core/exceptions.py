import logging

from rest_framework import status
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """Project-wide DRF exception handler with structured logging."""
    response = exception_handler(exc, context)

    view = context.get("view")
    request = context.get("request")

    if response is not None:
        # Log 5xx errors as errors; 4xx as warnings for visibility.
        status_code = response.status_code
        log_extra = {
            "view": type(view).__name__ if view else "unknown",
            "method": getattr(request, "method", "unknown"),
            "path": getattr(getattr(request, "_request", request), "path", "unknown"),
            "status_code": status_code,
            "exception_type": type(exc).__name__,
        }
        if status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
            logger.error("Unhandled server error: %s", exc, extra=log_extra, exc_info=True)
        elif status_code >= status.HTTP_400_BAD_REQUEST:
            logger.warning("Client error %s: %s", status_code, exc, extra=log_extra)
    else:
        # No response means DRF couldn't handle it — log as error.
        logger.error(
            "Unhandled exception not caught by DRF: %s",
            exc,
            extra={
                "view": type(view).__name__ if view else "unknown",
                "exception_type": type(exc).__name__,
            },
            exc_info=True,
        )

    return response
