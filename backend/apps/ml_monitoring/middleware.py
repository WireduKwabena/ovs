import logging
import time

from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)
_REQUEST_START_ATTR = "_request_start_time"


class PerformanceMonitoringMiddleware(MiddlewareMixin):
    """Attach request-duration telemetry and warn on slow requests."""

    def process_request(self, request):
        setattr(request, _REQUEST_START_ATTR, time.perf_counter())
        return None

    def process_response(self, request, response):
        start_time = getattr(request, _REQUEST_START_ATTR, None)
        if start_time is not None:
            duration = time.perf_counter() - start_time
            if duration > 1.0:
                logger.warning(
                    "Slow request: %s %s took %.2fs - Status: %s",
                    request.method,
                    request.path,
                    duration,
                    response.status_code,
                )

            response["X-Request-Duration"] = f"{duration:.3f}s"
        return response


class RequestLoggingMiddleware(MiddlewareMixin):
    """Log all API requests"""

    def process_request(self, request):
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            user_label = str(user)
        else:
            user_label = "Anonymous"

        logger.info(
            "Request: %s %s from %s User: %s",
            request.method,
            request.path,
            request.META.get("REMOTE_ADDR", "unknown"),
            user_label,
        )
        return None
