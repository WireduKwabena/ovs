from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from django.conf import settings
from django.db import connection
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import SystemHealthResponseSerializer

try:
    from drf_spectacular.utils import extend_schema
except ModuleNotFoundError:  # pragma: no cover - optional in lightweight envs
    def extend_schema(*args, **kwargs):
        def decorator(func):
            return func

        return decorator


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_database() -> dict[str, Any]:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return {"ok": True}
    except Exception as exc:  # pragma: no cover - depends on runtime infra
        return {"ok": False, "error": str(exc)}


def _check_redis_url(url: str) -> dict[str, Any]:
    if not url:
        return {"ok": None, "configured": False}
    try:
        import redis  # type: ignore
    except ModuleNotFoundError:
        return {
            "ok": False,
            "configured": True,
            "error": "redis package is not installed.",
        }

    try:
        client = redis.Redis.from_url(
            url,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        client.ping()
        return {"ok": True, "configured": True}
    except Exception as exc:  # pragma: no cover - depends on runtime infra
        return {"ok": False, "configured": True, "error": str(exc)}


class SystemHealthAPIView(APIView):
    """
    Lightweight runtime health endpoint for platform dependencies.
    """

    permission_classes = [AllowAny]
    authentication_classes: list[type] = []

    @extend_schema(
        responses=SystemHealthResponseSerializer,
        tags=["system"],
    )
    def get(self, request, *args, **kwargs):
        strict_runtime_checks = not bool(getattr(settings, "DEBUG", False))

        database_check = _check_database()
        redis_check = _check_redis_url(str(getattr(settings, "REDIS_URL", "")))

        broker_url = str(getattr(settings, "CELERY_BROKER_URL", "") or "")
        broker_scheme = urlparse(broker_url).scheme.lower()
        if broker_scheme.startswith("redis"):
            broker_check = _check_redis_url(broker_url)
        else:
            broker_check = {
                "ok": None if broker_url else False,
                "configured": bool(broker_url),
                "error": None if broker_url else "CELERY_BROKER_URL is not configured.",
            }

        critical_failures: list[str] = []
        if not database_check.get("ok"):
            critical_failures.append("database")

        if strict_runtime_checks:
            if bool(getattr(settings, "USE_REDIS", True)) and redis_check.get("ok") is False:
                critical_failures.append("redis")
            if broker_check.get("configured") and broker_check.get("ok") is False:
                critical_failures.append("celery_broker")

        overall_status = "ok" if not critical_failures else "degraded"
        http_status = 200 if not critical_failures else 503

        payload = {
            "status": overall_status,
            "timestamp": _utc_now_iso(),
            "strict_runtime_checks": strict_runtime_checks,
            "checks": {
                "database": database_check,
                "redis": redis_check,
                "celery_broker": broker_check,
            },
            "failures": critical_failures,
        }
        return Response(payload, status=http_status)
