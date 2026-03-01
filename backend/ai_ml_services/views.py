"""HTTP endpoints for AI/ML operational introspection."""

from __future__ import annotations

try:
    import cv2
except ModuleNotFoundError:  # pragma: no cover - optional at runtime
    cv2 = None

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - optional at runtime
    np = None
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.events import log_event
from apps.core.security import has_valid_service_token
from ai_ml_services.monitoring.model_monitor import model_monitor
from ai_ml_services.service import get_ai_service
from ai_ml_services.utils.pdf import pdf2image_kwargs

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


def _audit_ai_monitor_event(request, endpoint: str, changes: dict) -> None:
    log_event(
        request=request,
        action="other",
        entity_type="AIMonitorEndpoint",
        entity_id=endpoint,
        changes=changes,
    )


class MonitorHealthQuerySerializer(serializers.Serializer):
    model_name = serializers.CharField(required=False, default="default")


class DocumentClassificationUploadSerializer(serializers.Serializer):
    file = serializers.FileField(required=True)
    document_type = serializers.CharField(required=False, allow_blank=True, default="")
    top_k = serializers.IntegerField(required=False, default=3, min_value=1, max_value=5)


class SocialProfileItemSerializer(serializers.Serializer):
    platform = serializers.CharField(required=False, allow_blank=True, default="")
    url = serializers.CharField(required=False, allow_blank=True, default="")
    username = serializers.CharField(required=False, allow_blank=True, default="")
    display_name = serializers.CharField(required=False, allow_blank=True, default="")


class SocialProfileCheckSerializer(serializers.Serializer):
    case_id = serializers.CharField(required=False, allow_blank=True, default="")
    consent_provided = serializers.BooleanField(required=False, default=False)
    profiles = SocialProfileItemSerializer(many=True, required=True, allow_empty=False)


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

        _audit_ai_monitor_event(
            request,
            endpoint="health",
            changes={"model_name": model_name, "status": "ok"},
        )

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


class DocumentClassificationAPIView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = DocumentClassificationUploadSerializer

    @staticmethod
    def _decode_uploaded_image(uploaded_file):
        if cv2 is None or np is None:
            raise RuntimeError("OpenCV and NumPy are required for document classification uploads.")
        filename = str(getattr(uploaded_file, "name", "") or "").lower()
        content_type = str(getattr(uploaded_file, "content_type", "") or "").lower()
        payload = uploaded_file.read()
        if not payload:
            raise ValueError("Uploaded file is empty.")

        if filename.endswith(".pdf") or content_type == "application/pdf":
            from pdf2image import convert_from_bytes

            pages = convert_from_bytes(
                payload,
                first_page=1,
                last_page=1,
                **pdf2image_kwargs(),
            )
            if not pages:
                raise ValueError("Could not decode PDF first page.")
            return cv2.cvtColor(np.array(pages[0]), cv2.COLOR_RGB2BGR)

        buffer = np.frombuffer(payload, dtype=np.uint8)
        image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Unsupported or corrupted image file.")
        return image

    @extend_schema(
        request=DocumentClassificationUploadSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
        },
    )
    def post(self, request):
        """
        Classify document image into RVL-CDIP/MIDV-500 taxonomy.

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

        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        uploaded_file = serializer.validated_data["file"]
        document_type = serializer.validated_data.get("document_type", "")
        top_k = int(serializer.validated_data.get("top_k", 3))

        try:
            image = self._decode_uploaded_image(uploaded_file)
        except Exception as exc:
            return Response(
                {"detail": f"Unable to decode uploaded file: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = get_ai_service().classify_document_image(
            image=image,
            document_type=document_type,
            top_k=top_k,
        )

        _audit_ai_monitor_event(
            request,
            endpoint="classify-document",
            changes={
                "status": "ok",
                "document_type": document_type,
                "top_k": top_k,
                "filename": uploaded_file.name,
            },
        )

        return Response(
            {
                "status": "ok",
                "timestamp": timezone.now().isoformat(),
                "filename": uploaded_file.name,
                **result,
            },
            status=status.HTTP_200_OK,
        )


class SocialProfileCheckAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = SocialProfileCheckSerializer

    @extend_schema(
        request=SocialProfileCheckSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
        },
    )
    def post(self, request):
        """Run advisory social profile checks for a case."""
        if not (_is_admin_request(request) or has_valid_service_token(request)):
            return Response(
                {
                    "detail": "Forbidden. Use an admin account or a valid X-Service-Token."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        case_id = str(serializer.validated_data.get("case_id", "") or "").strip() or None
        consent_provided = bool(serializer.validated_data.get("consent_provided", False))
        profiles = serializer.validated_data.get("profiles", [])

        result = get_ai_service().check_social_profiles(
            profiles=profiles,
            consent_provided=consent_provided,
            case_id=case_id,
        )

        _audit_ai_monitor_event(
            request,
            endpoint="check-social-profiles",
            changes={
                "status": "ok",
                "case_id": case_id or result.get("case_id"),
                "consent_provided": bool(consent_provided),
                "profiles_requested": len(profiles),
                "profiles_checked": int(result.get("profiles_checked", 0) or 0),
                "overall_score": float(result.get("overall_score", 0.0) or 0.0),
                "risk_level": str(result.get("risk_level", "") or ""),
                "recommendation": str(result.get("recommendation", "") or ""),
            },
        )

        return Response(
            {
                "status": "ok",
                "timestamp": timezone.now().isoformat(),
                **result,
            },
            status=status.HTTP_200_OK,
        )


monitor_health_view = MonitorHealthAPIView.as_view()
document_classification_view = DocumentClassificationAPIView.as_view()
social_profile_check_view = SocialProfileCheckAPIView.as_view()

