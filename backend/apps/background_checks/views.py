import hashlib
import hmac

from django.conf import settings
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.permissions import IsGovernmentWorkflowOperator, scope_internal_queryset_to_tenant
from apps.core.policies.appointment_policy import can_view_internal_record
from apps.core.policies.registry_policy import is_platform_admin_actor

from .models import BackgroundCheck
from .serializers import (
    BackgroundCheckCreateSerializer,
    BackgroundCheckEventSerializer,
    BackgroundCheckSerializer,
    ProviderWebhookSerializer,
)
from .services import (
    DuplicateWebhookError,
    apply_webhook_update,
    refresh_background_check,
    retry_background_check,
    submit_background_check,
)
from .tasks import refresh_background_check_task


class BackgroundCheckViewSet(viewsets.ModelViewSet):
    queryset = BackgroundCheck.objects.select_related("case", "case__applicant", "submitted_by").all()
    permission_classes = [IsGovernmentWorkflowOperator]

    def get_serializer_class(self):
        if self.action == "create":
            return BackgroundCheckCreateSerializer
        return BackgroundCheckSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return BackgroundCheck.objects.none()

        queryset = super().get_queryset()
        queryset = scope_internal_queryset_to_tenant(
            queryset,
            request=self.request,
            organization_field="case__organization_id",
        )

        case_id = self.request.query_params.get("case_id")
        if case_id:
            queryset = queryset.filter(case__case_id=case_id)

        check_type = self.request.query_params.get("check_type")
        if check_type:
            queryset = queryset.filter(check_type=check_type)

        status_value = self.request.query_params.get("status")
        if status_value:
            queryset = queryset.filter(status=status_value)

        return queryset.order_by("-created_at")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        case = serializer.validated_data["case"]
        if not is_platform_admin_actor(request.user) and not can_view_internal_record(
            request.user,
            organization_id=getattr(case, "organization_id", None),
        ):
            raise ValidationError("You cannot submit background checks outside your organization scope.")

        run_async = serializer.validated_data.get("run_async", False)

        try:
            check = submit_background_check(
                case=case,
                check_type=serializer.validated_data["check_type"],
                submitted_by=request.user,
                provider_key=serializer.validated_data.get("provider_key"),
                request_payload=serializer.validated_data.get("request_payload"),
                consent_evidence=serializer.validated_data.get("consent_evidence"),
                request=request,
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        refresh_queued = False
        if run_async and check.status in {"submitted", "in_progress"}:
            refresh_background_check_task.delay(str(check.id))
            refresh_queued = True

        output = BackgroundCheckSerializer(check, context=self.get_serializer_context()).data
        output["refresh_queued"] = refresh_queued
        return Response(output, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        raise ValidationError("Background checks are immutable records. Use workflow actions instead.")

    def partial_update(self, request, *args, **kwargs):
        raise ValidationError("Background checks are immutable records. Use workflow actions instead.")

    def destroy(self, request, *args, **kwargs):
        raise ValidationError("Background checks cannot be deleted once created.")

    @action(detail=True, methods=["post"])
    def refresh(self, request, pk=None):
        check = self.get_object()

        updated = refresh_background_check(check, request=request)
        serializer = BackgroundCheckSerializer(updated, context=self.get_serializer_context())
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        check = self.get_object()
        try:
            retried = retry_background_check(check, submitted_by=request.user, request=request)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        serializer = BackgroundCheckSerializer(retried, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def events(self, request, pk=None):
        check = self.get_object()
        serializer = BackgroundCheckEventSerializer(check.events.all(), many=True)
        return Response(serializer.data)


class ProviderWebhookAPIView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "background_webhook"
    serializer_class = ProviderWebhookSerializer

    @staticmethod
    def _parse_provider_value_map(raw_value):
        mapping = {}
        for part in str(raw_value or "").split(","):
            item = part.strip()
            if not item or ":" not in item:
                continue
            key, value = item.split(":", 1)
            key = key.strip().lower()
            value = value.strip()
            if key and value:
                mapping[key] = value
        return mapping

    def _resolve_expected_token(self, provider_key):
        token_map = self._parse_provider_value_map(getattr(settings, "BACKGROUND_CHECK_WEBHOOK_PROVIDER_TOKENS", ""))
        return token_map.get(provider_key) or getattr(settings, "BACKGROUND_CHECK_WEBHOOK_TOKEN", "")

    def _resolve_signature_secret(self, provider_key):
        secret_map = self._parse_provider_value_map(getattr(settings, "BACKGROUND_CHECK_WEBHOOK_PROVIDER_SECRETS", ""))
        return secret_map.get(provider_key, "")

    def _verify_signature(self, request, provider_key):
        signature_required = bool(getattr(settings, "BACKGROUND_CHECK_WEBHOOK_REQUIRE_SIGNATURE", False))
        secret = self._resolve_signature_secret(provider_key)
        if not signature_required and not secret:
            return True
        if not secret:
            return False

        provided_signature = request.headers.get("X-Background-Webhook-Signature", "")
        if not provided_signature:
            return False

        expected_signature = hmac.new(secret.encode("utf-8"), request.body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(provided_signature, expected_signature)

    def post(self, request, provider_key):
        normalized_provider_key = str(provider_key or "").strip().lower()
        configured_token = self._resolve_expected_token(normalized_provider_key)
        if configured_token:
            provided_token = request.headers.get("X-Background-Webhook-Token", "")
            if provided_token != configured_token:
                return Response({"error": "Invalid webhook token."}, status=status.HTTP_403_FORBIDDEN)

        if not self._verify_signature(request, normalized_provider_key):
            return Response({"error": "Invalid webhook signature."}, status=status.HTTP_403_FORBIDDEN)

        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            check = apply_webhook_update(
                provider_key=normalized_provider_key,
                payload=serializer.validated_data,
                request=request,
            )
        except DuplicateWebhookError as exc:
            if exc.check is not None:
                output = BackgroundCheckSerializer(exc.check)
                return Response(output.data, status=status.HTTP_200_OK)
            return Response({"status": "duplicate"}, status=status.HTTP_200_OK)
        except LookupError as exc:
            if bool(getattr(settings, "BACKGROUND_CHECK_WEBHOOK_ACK_DEAD_LETTER", True)):
                return Response({"status": "accepted", "detail": str(exc)}, status=status.HTTP_202_ACCEPTED)
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as exc:
            if bool(getattr(settings, "BACKGROUND_CHECK_WEBHOOK_ACK_DEAD_LETTER", True)):
                return Response({"status": "accepted", "detail": str(exc)}, status=status.HTTP_202_ACCEPTED)
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        output = BackgroundCheckSerializer(check)
        return Response(output.data, status=status.HTTP_200_OK)
