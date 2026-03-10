from django.db import transaction
from rest_framework.exceptions import ValidationError
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied

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

from apps.core.permissions import (
    IsGovernmentWorkflowOperator,
    can_access_organization_id,
    get_request_active_organization_id,
    is_platform_admin_user,
    scope_internal_queryset_to_tenant,
)
from apps.authentication.permissions import RequiresRecentAuth

from .models import AppointmentRecord, ApprovalStage, ApprovalStageTemplate
from .permissions import (
    IsAppointingAuthorityOrAdmin,
    IsCommitteeMemberOrAdmin,
    IsPublicationOfficerOrAuthorityOrAdmin,
    IsStageActorOrAdmin,
)
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
from .public_services import (
    apply_public_appointment_query_params,
    public_open_appointments_queryset,
    published_appointments_queryset,
)

LEGACY_PUBLIC_ENDPOINT_SUNSET = "Thu, 31 Dec 2026 23:59:59 GMT"


def _apply_legacy_public_endpoint_headers(response: Response, *, successor_path: str) -> Response:
    response["Deprecation"] = "true"
    response["Sunset"] = LEGACY_PUBLIC_ENDPOINT_SUNSET
    response["Link"] = f'<{successor_path}>; rel="successor-version"'
    response["X-Deprecated-Endpoint"] = "true"
    return response


class ApprovalStageTemplateViewSet(viewsets.ModelViewSet):
    queryset = ApprovalStageTemplate.objects.select_related("organization").prefetch_related("stages").all()
    serializer_class = ApprovalStageTemplateSerializer
    permission_classes = [IsGovernmentWorkflowOperator]
    filterset_fields = ["organization", "exercise_type"]
    search_fields = ["name", "exercise_type"]
    ordering_fields = ["name", "created_at"]

    def get_queryset(self):
        queryset = super().get_queryset()
        return scope_internal_queryset_to_tenant(
            queryset,
            request=self.request,
            organization_field="organization_id",
        )

    def perform_create(self, serializer):
        user = self.request.user
        requested_org = serializer.validated_data.get("organization")
        if not is_platform_admin_user(user):
            if requested_org is not None and not can_access_organization_id(
                user,
                requested_org.id,
                allow_membershipless_fallback=False,
            ):
                raise PermissionDenied("You cannot create approval templates for another organization.")
            active_org_id = get_request_active_organization_id(self.request)
            if requested_org is None and not active_org_id:
                raise PermissionDenied("Active organization context is required to create approval templates.")
            if requested_org is None and active_org_id:
                serializer.save(created_by=self.request.user, organization_id=active_org_id)
                return
        serializer.save(created_by=self.request.user)


class ApprovalStageViewSet(viewsets.ModelViewSet):
    queryset = ApprovalStage.objects.select_related("template", "template__organization", "committee").all()
    serializer_class = ApprovalStageSerializer
    permission_classes = [IsGovernmentWorkflowOperator]
    filterset_fields = ["template", "committee", "required_role", "maps_to_status", "is_required"]
    search_fields = ["name", "required_role", "maps_to_status"]
    ordering_fields = ["order", "name"]

    def get_queryset(self):
        queryset = super().get_queryset()
        return scope_internal_queryset_to_tenant(
            queryset,
            request=self.request,
            organization_field="template__organization_id",
        )

    def perform_create(self, serializer):
        user = self.request.user
        template = serializer.validated_data.get("template")
        committee = serializer.validated_data.get("committee")
        if not is_platform_admin_user(user) and template is not None and not can_access_organization_id(
            user,
            template.organization_id,
            allow_membershipless_fallback=False,
        ):
            raise PermissionDenied("You cannot create stages for templates outside your organization.")
        if (
            not is_platform_admin_user(user)
            and committee is not None
            and not can_access_organization_id(
                user,
                committee.organization_id,
                allow_membershipless_fallback=False,
            )
        ):
            raise PermissionDenied("You cannot assign a committee outside your organization.")
        serializer.save()

    def perform_update(self, serializer):
        user = self.request.user
        instance = serializer.instance
        template = serializer.validated_data.get("template") or instance.template
        committee = serializer.validated_data.get("committee") if "committee" in serializer.validated_data else instance.committee
        if not is_platform_admin_user(user) and template is not None and not can_access_organization_id(
            user,
            template.organization_id,
            allow_membershipless_fallback=False,
        ):
            raise PermissionDenied("You cannot update stages for templates outside your organization.")
        if (
            not is_platform_admin_user(user)
            and committee is not None
            and not can_access_organization_id(
                user,
                committee.organization_id,
                allow_membershipless_fallback=False,
            )
        ):
            raise PermissionDenied("You cannot assign a committee outside your organization.")
        serializer.save()


class AppointmentRecordViewSet(viewsets.ModelViewSet):
    queryset = AppointmentRecord.objects.select_related(
        "organization",
        "committee",
        "position",
        "position__organization",
        "nominee",
        "nominee__organization",
        "appointment_exercise",
        "appointment_exercise__organization",
        "nominated_by_user",
        "vetting_case",
        "vetting_case__organization",
        "final_decision_by_user",
        "publication",
    ).prefetch_related("stage_actions")
    serializer_class = AppointmentRecordSerializer
    permission_classes = [IsGovernmentWorkflowOperator]
    filterset_fields = [
        "status",
        "is_public",
        "organization",
        "committee",
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

    def get_queryset(self):
        queryset = super().get_queryset()
        return scope_internal_queryset_to_tenant(
            queryset,
            request=self.request,
            organization_field="organization_id",
        )

    def perform_create(self, serializer):
        try:
            with transaction.atomic():
                user = self.request.user
                requested_org = serializer.validated_data.get("organization")
                requested_committee = serializer.validated_data.get("committee")
                position = serializer.validated_data.get("position")
                exercise = serializer.validated_data.get("appointment_exercise")
                nominee = serializer.validated_data.get("nominee")

                resolved_org_id = (
                    str(getattr(requested_org, "id", "") or "")
                    or str(getattr(exercise, "organization_id", "") or "")
                    or str(getattr(position, "organization_id", "") or "")
                    or str(getattr(nominee, "organization_id", "") or "")
                    or str(get_request_active_organization_id(self.request) or "")
                )
                resolved_org_id = resolved_org_id or None

                if not is_platform_admin_user(user):
                    if requested_org is not None and not can_access_organization_id(
                        user,
                        requested_org.id,
                        allow_membershipless_fallback=False,
                    ):
                        raise ValidationError("You cannot create appointments for another organization.")
                    if (
                        requested_committee is not None
                        and not can_access_organization_id(
                            user,
                            requested_committee.organization_id,
                            allow_membershipless_fallback=False,
                        )
                    ):
                        raise ValidationError("You cannot assign an appointment committee outside your organization.")
                    if resolved_org_id and not can_access_organization_id(
                        user,
                        resolved_org_id,
                        allow_membershipless_fallback=False,
                    ):
                        raise ValidationError("You cannot create appointments for another organization.")
                    if not resolved_org_id:
                        raise ValidationError("Active organization context is required to create appointments.")

                if resolved_org_id:
                    appointment = serializer.save(
                        nominated_by_user=self.request.user,
                        organization_id=resolved_org_id,
                    )
                else:
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
                        "organization_id": str(appointment.organization_id or ""),
                        "committee_id": str(appointment.committee_id or ""),
                        "position_id": str(appointment.position_id),
                        "nominee_id": str(appointment.nominee_id),
                        "status": appointment.status,
                    },
                )
        except LinkageValidationError as exc:
            raise ValidationError({"non_field_errors": [str(exc)]}) from exc

    def perform_update(self, serializer):
        instance = serializer.instance
        user = self.request.user
        if not is_platform_admin_user(user) and not can_access_organization_id(
            user,
            instance.organization_id,
            allow_membershipless_fallback=False,
        ):
            raise PermissionDenied("You cannot update appointments outside your organization scope.")

        requested_org = serializer.validated_data.get("organization")
        requested_committee = serializer.validated_data.get("committee")
        if not is_platform_admin_user(user) and requested_org is not None and not can_access_organization_id(
            user,
            requested_org.id,
            allow_membershipless_fallback=False,
        ):
            raise PermissionDenied("You cannot move this appointment to another organization.")
        if (
            not is_platform_admin_user(user)
            and requested_committee is not None
            and not can_access_organization_id(
                user,
                requested_committee.organization_id,
                allow_membershipless_fallback=False,
            )
        ):
            raise PermissionDenied("You cannot assign appointment committee outside your organization.")

        changed_fields = list(serializer.validated_data.keys())
        before = {field: getattr(instance, field, None) for field in changed_fields}
        save_kwargs = {}
        if (
            not is_platform_admin_user(user)
            and instance.organization_id is None
            and "organization" not in serializer.validated_data
        ):
            active_org_id = get_request_active_organization_id(self.request)
            if active_org_id:
                save_kwargs["organization_id"] = active_org_id

        appointment = serializer.save(**save_kwargs)
        after = {field: getattr(appointment, field, None) for field in changed_fields}
        log_event(
            request=self.request,
            action="update",
            entity_type="AppointmentRecord",
            entity_id=str(appointment.id),
            changes={
                "event": APPOINTMENT_RECORD_UPDATED_EVENT,
                "organization_id": str(appointment.organization_id or ""),
                "committee_id": str(appointment.committee_id or ""),
                "changed_fields": changed_fields,
                "before": before,
                "after": after,
            },
        )

    def perform_destroy(self, instance):
        user = self.request.user
        if not is_platform_admin_user(user) and not can_access_organization_id(
            user,
            instance.organization_id,
            allow_membershipless_fallback=False,
        ):
            raise PermissionDenied("You cannot delete appointments outside your organization scope.")
        snapshot = {
            "organization_id": str(instance.organization_id) if instance.organization_id else "",
            "committee_id": str(instance.committee_id) if instance.committee_id else "",
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
                "organization_id": str(instance.organization_id or ""),
                "committee_id": str(instance.committee_id or ""),
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

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAppointingAuthorityOrAdmin, RequiresRecentAuth],
        url_path="appoint",
    )
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
                "organization_id": str(appointment.organization_id or ""),
                "committee_id": str(appointment.committee_id or ""),
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
        rows = appointment.stage_actions.select_related(
            "stage",
            "stage__committee",
            "actor",
            "committee_membership",
            "committee_membership__committee",
        ).all()
        serializer = AppointmentStageActionSerializer(rows, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsPublicationOfficerOrAuthorityOrAdmin, RequiresRecentAuth],
        url_path="publish",
    )
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
        permission_classes=[IsPublicationOfficerOrAuthorityOrAdmin, RequiresRecentAuth],
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

    @action(detail=True, methods=["get"], permission_classes=[IsGovernmentWorkflowOperator], url_path="publication")
    def publication_detail(self, request, pk=None):
        appointment = self.get_object()
        publication = ensure_publication_record_for_appointment(appointment=appointment)
        return Response(AppointmentPublicationSerializer(publication).data, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[permissions.AllowAny],
        renderer_classes=[JSONRenderer],
        url_path="gazette-feed",
    )
    def gazette_feed(self, request):
        queryset = published_appointments_queryset(require_gazette_number=True)
        queryset = apply_public_appointment_query_params(
            queryset,
            query_params=request.query_params,
        )
        serializer = PublicAppointmentRecordSerializer(queryset, many=True)
        response = Response(serializer.data, status=status.HTTP_200_OK)
        return _apply_legacy_public_endpoint_headers(
            response,
            successor_path="/api/public/transparency/appointments/gazette-feed/",
        )

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[permissions.AllowAny],
        renderer_classes=[JSONRenderer],
        url_path="open",
    )
    def open_appointments(self, request):
        queryset = public_open_appointments_queryset()
        queryset = apply_public_appointment_query_params(
            queryset,
            query_params=request.query_params,
        )
        serializer = PublicAppointmentRecordSerializer(queryset, many=True)
        response = Response(serializer.data, status=status.HTTP_200_OK)
        return _apply_legacy_public_endpoint_headers(
            response,
            successor_path="/api/public/transparency/appointments/open/",
        )
