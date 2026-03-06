from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import IsHRManagerOrAdmin

from .models import AppointmentRecord, ApprovalStage, ApprovalStageTemplate
from .permissions import IsAppointingAuthorityOrAdmin, IsCommitteeMemberOrAdmin, IsStageActorOrAdmin
from .serializers import (
    AppointmentAdvanceStageSerializer,
    AppointmentRecordSerializer,
    AppointmentStageActionSerializer,
    ApprovalStageSerializer,
    ApprovalStageTemplateSerializer,
    PublicAppointmentRecordSerializer,
)
from .services import InvalidTransitionError, StageAuthorizationError, advance_stage, ensure_vetting_linkage_for_appointment


class ApprovalStageTemplateViewSet(viewsets.ModelViewSet):
    queryset = ApprovalStageTemplate.objects.prefetch_related("stages").all()
    serializer_class = ApprovalStageTemplateSerializer
    permission_classes = [IsHRManagerOrAdmin]
    filterset_fields = ["exercise_type"]
    search_fields = ["name", "exercise_type"]
    ordering_fields = ["name", "created_at"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class ApprovalStageViewSet(viewsets.ModelViewSet):
    queryset = ApprovalStage.objects.select_related("template").all()
    serializer_class = ApprovalStageSerializer
    permission_classes = [IsHRManagerOrAdmin]
    filterset_fields = ["template", "required_role", "maps_to_status", "is_required"]
    search_fields = ["name", "required_role", "maps_to_status"]
    ordering_fields = ["order", "name"]


class AppointmentRecordViewSet(viewsets.ModelViewSet):
    queryset = AppointmentRecord.objects.select_related(
        "position",
        "nominee",
        "appointment_exercise",
        "nominated_by_user",
        "vetting_case",
        "final_decision_by_user",
    ).prefetch_related("stage_actions")
    serializer_class = AppointmentRecordSerializer
    permission_classes = [IsHRManagerOrAdmin]
    filterset_fields = [
        "status",
        "is_public",
        "position",
        "nominee",
        "appointment_exercise",
    ]
    search_fields = [
        "position__title",
        "nominee__full_name",
        "nominated_by_display",
        "nominated_by_org",
        "gazette_number",
    ]
    ordering_fields = ["created_at", "nomination_date", "appointment_date", "updated_at"]

    def perform_create(self, serializer):
        appointment = serializer.save(nominated_by_user=self.request.user)
        ensure_vetting_linkage_for_appointment(appointment=appointment, actor=self.request.user)

    @action(detail=True, methods=["post"], permission_classes=[IsStageActorOrAdmin], url_path="advance-stage")
    def advance_stage_action(self, request, pk=None):
        appointment = self.get_object()
        payload = AppointmentAdvanceStageSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        stage = None
        stage_id = payload.validated_data.get("stage_id")
        if stage_id:
            stage = ApprovalStage.objects.filter(id=stage_id).first()
            if stage is None:
                return Response({"error": "Approval stage not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            appointment = advance_stage(
                appointment=appointment,
                new_status=payload.validated_data["status"],
                actor=request.user,
                stage=stage,
                reason_note=payload.validated_data.get("reason_note", ""),
                evidence_links=payload.validated_data.get("evidence_links", []),
                request=request,
            )
        except InvalidTransitionError as exc:
            return Response({"error": str(exc), "code": "invalid_transition"}, status=status.HTTP_400_BAD_REQUEST)
        except StageAuthorizationError as exc:
            return Response({"error": str(exc), "code": "insufficient_role"}, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(appointment)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], permission_classes=[IsAppointingAuthorityOrAdmin], url_path="appoint")
    def appoint(self, request, pk=None):
        appointment = self.get_object()
        try:
            appointment = advance_stage(
                appointment=appointment,
                new_status="appointed",
                actor=request.user,
                reason_note=request.data.get("reason_note", ""),
                evidence_links=request.data.get("evidence_links", []),
                request=request,
            )
        except InvalidTransitionError as exc:
            return Response({"error": str(exc), "code": "invalid_transition"}, status=status.HTTP_400_BAD_REQUEST)
        except StageAuthorizationError as exc:
            return Response({"error": str(exc), "code": "insufficient_role"}, status=status.HTTP_403_FORBIDDEN)
        return Response(self.get_serializer(appointment).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], permission_classes=[IsAppointingAuthorityOrAdmin], url_path="reject")
    def reject(self, request, pk=None):
        appointment = self.get_object()
        try:
            appointment = advance_stage(
                appointment=appointment,
                new_status="rejected",
                actor=request.user,
                reason_note=request.data.get("reason_note", ""),
                evidence_links=request.data.get("evidence_links", []),
                request=request,
            )
        except InvalidTransitionError as exc:
            return Response({"error": str(exc), "code": "invalid_transition"}, status=status.HTTP_400_BAD_REQUEST)
        except StageAuthorizationError as exc:
            return Response({"error": str(exc), "code": "insufficient_role"}, status=status.HTTP_403_FORBIDDEN)
        return Response(self.get_serializer(appointment).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="ensure-vetting-linkage")
    def ensure_vetting_linkage_action(self, request, pk=None):
        appointment = self.get_object()
        appointment = ensure_vetting_linkage_for_appointment(appointment=appointment, actor=request.user)
        serializer = self.get_serializer(appointment)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], permission_classes=[IsCommitteeMemberOrAdmin], url_path="stage-actions")
    def stage_actions(self, request, pk=None):
        appointment = self.get_object()
        rows = appointment.stage_actions.select_related("stage", "actor").all()
        serializer = AppointmentStageActionSerializer(rows, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny], url_path="gazette-feed")
    def gazette_feed(self, request):
        queryset = self.filter_queryset(
            self.get_queryset().filter(is_public=True).exclude(gazette_number="")
        )
        serializer = PublicAppointmentRecordSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny], url_path="open")
    def open_appointments(self, request):
        queryset = self.filter_queryset(
            self.get_queryset().filter(
                status__in={"nominated", "under_vetting", "committee_review", "confirmation_pending"},
                is_public=True,
            )
        )
        serializer = PublicAppointmentRecordSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
