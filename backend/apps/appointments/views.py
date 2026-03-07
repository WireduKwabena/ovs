from django.db import transaction
from rest_framework.exceptions import ValidationError
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.audit.contracts import (
    APPOINTMENT_RECORD_CREATED_EVENT,
    APPOINTMENT_RECORD_DELETED_EVENT,
    APPOINTMENT_RECORD_UPDATED_EVENT,
    APPOINTMENT_VETTING_LINKAGE_ENSURED_EVENT,
)
try:
    from apps.audit.events import log_event
except Exception:  # pragma: no cover - audit app may be optional in some setups
    def log_event(**kwargs):  # type: ignore
        return False

from apps.core.permissions import IsHRManagerOrAdmin

from .models import AppointmentRecord, ApprovalStage, ApprovalStageTemplate
from .permissions import IsAppointingAuthorityOrAdmin, IsCommitteeMemberOrAdmin, IsStageActorOrAdmin
from .serializers import (
    AppointmentAdvanceStageSerializer,
    AppointmentPublicationSerializer,
    AppointmentPublishSerializer,
    AppointmentRecordSerializer,
    AppointmentRevokePublicationSerializer,
    AppointmentStageActionSerializer,
    ApprovalStageSerializer,
    ApprovalStageTemplateSerializer,
    PublicAppointmentRecordSerializer,
)
from .services import (
    InvalidTransitionError,
    LinkageValidationError,
    PublicationLifecycleError,
    StageAuthorizationError,
    advance_stage,
    ensure_publication_record_for_appointment,
    ensure_vetting_linkage_for_appointment,
    notify_nomination_created,
    publish_appointment_record,
    revoke_appointment_publication,
)


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
        "publication",
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
        try:
            with transaction.atomic():
                appointment = serializer.save(nominated_by_user=self.request.user)
                ensure_vetting_linkage_for_appointment(appointment=appointment, actor=self.request.user)
                ensure_publication_record_for_appointment(appointment=appointment)
                notify_nomination_created(appointment=appointment, actor=self.request.user, request=self.request)
                log_event(
                    request=self.request,
                    action="create",
                    entity_type="AppointmentRecord",
                    entity_id=str(appointment.id),
                    changes={
                        "event": APPOINTMENT_RECORD_CREATED_EVENT,
                        "position_id": str(appointment.position_id),
                        "nominee_id": str(appointment.nominee_id),
                        "status": appointment.status,
                    },
                )
        except LinkageValidationError as exc:
            raise ValidationError({"non_field_errors": [str(exc)]}) from exc

    def perform_update(self, serializer):
        instance = serializer.instance
        changed_fields = list(serializer.validated_data.keys())
        before = {field: getattr(instance, field, None) for field in changed_fields}
        appointment = serializer.save()
        after = {field: getattr(appointment, field, None) for field in changed_fields}
        log_event(
            request=self.request,
            action="update",
            entity_type="AppointmentRecord",
            entity_id=str(appointment.id),
            changes={
                "event": APPOINTMENT_RECORD_UPDATED_EVENT,
                "changed_fields": changed_fields,
                "before": before,
                "after": after,
            },
        )

    def perform_destroy(self, instance):
        snapshot = {
            "position_id": str(instance.position_id),
            "nominee_id": str(instance.nominee_id),
            "status": instance.status,
            "is_public": instance.is_public,
        }
        entity_id = str(instance.id)
        super().perform_destroy(instance)
        log_event(
            request=self.request,
            action="delete",
            entity_type="AppointmentRecord",
            entity_id=entity_id,
            changes={
                "event": APPOINTMENT_RECORD_DELETED_EVENT,
                "snapshot": snapshot,
            },
        )

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
        stage = None
        stage_id = request.data.get("stage_id")
        if stage_id:
            stage = ApprovalStage.objects.filter(id=stage_id).first()
            if stage is None:
                return Response({"error": "Approval stage not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            appointment = advance_stage(
                appointment=appointment,
                new_status="appointed",
                actor=request.user,
                stage=stage,
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
        stage = None
        stage_id = request.data.get("stage_id")
        if stage_id:
            stage = ApprovalStage.objects.filter(id=stage_id).first()
            if stage is None:
                return Response({"error": "Approval stage not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            appointment = advance_stage(
                appointment=appointment,
                new_status="rejected",
                actor=request.user,
                stage=stage,
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
        try:
            appointment = ensure_vetting_linkage_for_appointment(appointment=appointment, actor=request.user)
        except LinkageValidationError as exc:
            return Response({"error": str(exc), "code": "linkage_invalid"}, status=status.HTTP_400_BAD_REQUEST)
        log_event(
            request=request,
            action="update",
            entity_type="AppointmentRecord",
            entity_id=str(appointment.id),
            changes={
                "event": APPOINTMENT_VETTING_LINKAGE_ENSURED_EVENT,
                "vetting_case_id": str(appointment.vetting_case_id) if appointment.vetting_case_id else "",
                "appointment_exercise_id": str(appointment.appointment_exercise_id)
                if appointment.appointment_exercise_id
                else "",
            },
        )
        serializer = self.get_serializer(appointment)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], permission_classes=[IsCommitteeMemberOrAdmin], url_path="stage-actions")
    def stage_actions(self, request, pk=None):
        appointment = self.get_object()
        rows = appointment.stage_actions.select_related("stage", "actor").all()
        serializer = AppointmentStageActionSerializer(rows, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], permission_classes=[IsAppointingAuthorityOrAdmin], url_path="publish")
    def publish(self, request, pk=None):
        appointment = self.get_object()
        payload = AppointmentPublishSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        try:
            publication = publish_appointment_record(
                appointment=appointment,
                actor=request.user,
                publication_reference=payload.validated_data.get("publication_reference", ""),
                publication_document_hash=payload.validated_data.get("publication_document_hash", ""),
                publication_notes=payload.validated_data.get("publication_notes", ""),
                gazette_number=payload.validated_data.get("gazette_number"),
                gazette_date=payload.validated_data.get("gazette_date"),
                request=request,
            )
        except PublicationLifecycleError as exc:
            return Response({"error": str(exc), "code": "publication_invalid"}, status=status.HTTP_400_BAD_REQUEST)

        return Response(AppointmentPublicationSerializer(publication).data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAppointingAuthorityOrAdmin],
        url_path="revoke-publication",
    )
    def revoke_publication(self, request, pk=None):
        appointment = self.get_object()
        payload = AppointmentRevokePublicationSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        try:
            publication = revoke_appointment_publication(
                appointment=appointment,
                actor=request.user,
                revocation_reason=payload.validated_data["revocation_reason"],
                make_private=payload.validated_data.get("make_private", True),
                request=request,
            )
        except PublicationLifecycleError as exc:
            return Response({"error": str(exc), "code": "publication_invalid"}, status=status.HTTP_400_BAD_REQUEST)

        return Response(AppointmentPublicationSerializer(publication).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], permission_classes=[IsHRManagerOrAdmin], url_path="publication")
    def publication_detail(self, request, pk=None):
        appointment = self.get_object()
        publication = ensure_publication_record_for_appointment(appointment=appointment)
        return Response(AppointmentPublicationSerializer(publication).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny], url_path="gazette-feed")
    def gazette_feed(self, request):
        queryset = self.filter_queryset(
            self.get_queryset().filter(is_public=True, publication__status="published").exclude(gazette_number="")
        )
        serializer = PublicAppointmentRecordSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny], url_path="open")
    def open_appointments(self, request):
        queryset = self.filter_queryset(
            self.get_queryset().filter(
                status__in={"nominated", "under_vetting", "committee_review", "confirmation_pending"},
                is_public=True,
                publication__status="published",
            )
        )
        serializer = PublicAppointmentRecordSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
