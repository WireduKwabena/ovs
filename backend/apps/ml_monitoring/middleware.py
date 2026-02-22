# backend/apps/monitoring/middleware.py
# Performance monitoring middleware

import time
import logging
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)

class PerformanceMonitoringMiddleware(MiddlewareMixin):
    """
    Monitor API performance
    From: Best practices for production monitoring
    """
    
    def process_request(self, request):
        request._start_time = time.time()
        return None
    
    def process_response(self, request, response):
        if hasattr(request, '_start_time'):
            duration = time.time() - request._start_time
            
            # Log slow requests (> 1 second)
            if duration > 1.0:
                logger.warning(
                    f"Slow request: {request.method} {request.path} "
                    f"took {duration:.2f}s - Status: {response.status_code}"
                )
            
            # Add performance header
            response['X-Request-Duration'] = f"{duration:.3f}s"
        
        return response


class RequestLoggingMiddleware(MiddlewareMixin):
    """Log all API requests"""
    
    def process_request(self, request):
        logger.info(
            f"Request: {request.method} {request.path} "
            f"from {request.META.get('REMOTE_ADDR')} "
            f"User: {request.user if request.user.is_authenticated else 'Anonymous'}"
        )
        return None