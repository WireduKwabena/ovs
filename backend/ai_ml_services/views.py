"""HTTP endpoints for AI/ML operational introspection."""

from __future__ import annotations

from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.security import has_valid_service_token
from ai_ml_services.monitoring.model_monitor import model_monitor

try:
    from drf_spectacular.types import OpenApiTypes
    from drf_spectacular.utils import extend_schema
except ModuleNotFoundError:  # pragma: no cover - optional in some setups
    class _OpenApiTypes:
        OBJECT = dict

    OpenApiTypes = _OpenApiTypes()

    def extend_schema(*args, **kwargs):
        def decorator(func):
            return func

        return decorator


def _is_admin_request(request) -> bool:
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return False
    return bool(
        getattr(user, "is_staff", False)
        or getattr(user, "is_superuser", False)
        or getattr(user, "user_type", None) in {"admin", "hr_manager"}
    )

class MonitorHealthQuerySerializer(serializers.Serializer):
    model_name = serializers.CharField(required=False, default="default")


class MonitorHealthAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = MonitorHealthQuerySerializer

    @extend_schema(
        parameters=[MonitorHealthQuerySerializer],
        responses={
            200: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
        },
    )
    def get(self, request):
        """
        Runtime health snapshot for AI monitoring backend.

        Access:
        - authenticated admin/staff user, or
        - valid X-Service-Token header (matches SERVICE_TOKEN setting)
        """
        if not (_is_admin_request(request) or has_valid_service_token(request)):
            return Response(
                {
                    "detail": "Forbidden. Use an admin account or a valid X-Service-Token."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.serializer_class(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        model_name = serializer.validated_data["model_name"]

        metrics = model_monitor.get_metrics(model_name=model_name)
        drift = model_monitor.check_data_drift(model_name=model_name)

        return Response(
            {
                "status": "ok",
                "timestamp": timezone.now().isoformat(),
                "model_name": model_name,
                "monitor": {
                    "enabled": model_monitor.enabled,
                    "backend": model_monitor.backend,
                    "use_redis": model_monitor.use_redis,
                    "redis_configured": bool(model_monitor.redis_url),
                },
                "metrics": metrics,
                "drift": drift,
            },
            status=status.HTTP_200_OK,
        )


monitor_health_view = MonitorHealthAPIView.as_view()
