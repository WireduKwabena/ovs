from django.conf import settings
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsHRManagerOrAdmin

from .models import BackgroundCheck
from .serializers import (
    BackgroundCheckCreateSerializer,
    BackgroundCheckEventSerializer,
    BackgroundCheckSerializer,
    ProviderWebhookSerializer,
)
from .services import apply_webhook_update, refresh_background_check, submit_background_check
from .tasks import refresh_background_check_task


class BackgroundCheckViewSet(viewsets.ModelViewSet):
    queryset = BackgroundCheck.objects.select_related("case", "case__applicant", "submitted_by").all()
    permission_classes = [IsHRManagerOrAdmin]

    def get_serializer_class(self):
        if self.action == "create":
            return BackgroundCheckCreateSerializer
        return BackgroundCheckSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return BackgroundCheck.objects.none()

        queryset = super().get_queryset()

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

    @action(detail=True, methods=["post"])
    def refresh(self, request, pk=None):
        check = self.get_object()

        updated = refresh_background_check(check, request=request)
        serializer = BackgroundCheckSerializer(updated, context=self.get_serializer_context())
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def events(self, request, pk=None):
        check = self.get_object()
        serializer = BackgroundCheckEventSerializer(check.events.all(), many=True)
        return Response(serializer.data)


class ProviderWebhookAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = ProviderWebhookSerializer

    def post(self, request, provider_key):
        configured_token = getattr(settings, "BACKGROUND_CHECK_WEBHOOK_TOKEN", "")
        if configured_token:
            provided_token = request.headers.get("X-Background-Webhook-Token", "")
            if provided_token != configured_token:
                return Response({"error": "Invalid webhook token."}, status=status.HTTP_403_FORBIDDEN)

        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            check = apply_webhook_update(
                provider_key=provider_key,
                payload=serializer.validated_data,
                request=request,
            )
        except LookupError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        output = BackgroundCheckSerializer(check)
        return Response(output.data, status=status.HTTP_200_OK)
