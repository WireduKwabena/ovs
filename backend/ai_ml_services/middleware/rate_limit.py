"""Django middleware rate limiting for AI/ML endpoints."""

from __future__ import annotations

import logging
import os
import time
from typing import Optional, Tuple

import redis
from django.conf import settings
from django.http import JsonResponse

logger = logging.getLogger(__name__)


class RateLimiter:
    """Redis-backed sliding-window rate limiter."""

    def __init__(self, requests_per_minute: int = 60, redis_url: Optional[str] = None):
        self.requests_per_minute = requests_per_minute
        self.window_seconds = 60
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/1")
        self.redis_client = None

        try:
            self.redis_client = redis.from_url(self.redis_url)
            self.redis_client.ping()
            logger.info(
                "Redis rate limiter connected successfully to %s.", self.redis_url
            )
        except redis.exceptions.ConnectionError as exc:
            logger.error(
                "Could not connect to Redis for rate limiting at %s: %s. "
                "Rate limiting will be disabled.",
                self.redis_url,
                exc,
                exc_info=True,
            )
            self.redis_client = None
        except Exception as exc:  # pragma: no cover - defensive
            logger.error(
                "Unexpected Redis rate limiter setup error: %s. "
                "Rate limiting will be disabled.",
                exc,
                exc_info=True,
            )
            self.redis_client = None

    def check_rate_limit(self, client_id: str) -> Tuple[bool, Optional[int]]:
        """Return (allowed, retry_after_seconds)."""
        if not self.redis_client:
            return True, None

        now = int(time.time())
        key = f"rate_limit:{client_id}"
        member = f"{now}:{time.time_ns()}"

        try:
            pipe = self.redis_client.pipeline()
            pipe.zadd(key, {member: now})
            pipe.zremrangebyscore(key, 0, now - self.window_seconds)
            pipe.zcard(key)
            pipe.expire(key, self.window_seconds + 5)
            _, _, count, _ = pipe.execute()

            if count > self.requests_per_minute:
                return False, self.window_seconds
            return True, None
        except redis.exceptions.RedisError as exc:
            logger.error(
                "Redis error during rate limit check for client_id=%s: %s. Allowing request.",
                client_id,
                exc,
                exc_info=True,
            )
            return True, None


class DjangoRateLimitMiddleware:
    """Apply rate limiting to configured AI/ML paths."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.path_prefixes = tuple(
            getattr(settings, "AI_ML_RATE_LIMIT_PATH_PREFIXES", ("/api/",))
        )
        self.rate_limiter = RateLimiter(
            requests_per_minute=getattr(settings, "AI_ML_RATE_LIMIT_PER_MINUTE", 120),
            redis_url=getattr(settings, "AI_ML_RATE_LIMIT_REDIS_URL", None),
        )

    def __call__(self, request):
        path = request.path or "/"
        if self.path_prefixes and not path.startswith(self.path_prefixes):
            return self.get_response(request)

        client_id = self._extract_client_id(request)
        allowed, retry_after = self.rate_limiter.check_rate_limit(client_id)
        if not allowed:
            response = JsonResponse(
                {"detail": "Rate limit exceeded. Please try again later."},
                status=429,
            )
            if retry_after:
                response["Retry-After"] = str(retry_after)
            return response

        return self.get_response(request)

    @staticmethod
    def _extract_client_id(request) -> str:
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")
