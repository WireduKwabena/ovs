from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.candidates.models import Candidate
from apps.core.permissions import (
    BlockPlatformAdminOrgWorkflowMixin,
    IsRegistryOperatorOrAdmin,
    get_request_active_organization_id,
    scope_internal_queryset_to_tenant,
)
from apps.core.policies.appointment_policy import can_view_internal_record
from apps.core.policies.registry_policy import (
    can_manage_registry,
    can_manage_registry_record,
    is_platform_admin_actor,
)
from apps.audit.contracts import (
    PERSONNEL_LINKED_CANDIDATE_EVENT,
    PERSONNEL_RECORD_CREATED_EVENT,
    PERSONNEL_RECORD_DELETED_EVENT,
    PERSONNEL_RECORD_UPDATED_EVENT,
)
try:
    from apps.audit.events import log_event
except Exception:  # pragma: no cover - audit app may be optional in some setups
    def log_event(**kwargs):  # type: ignore
        return False

from .models import PersonnelRecord
from .serializers import PersonnelRecordSerializer, PublicPersonnelRecordSerializer


class PersonnelRecordViewSet(BlockPlatformAdminOrgWorkflowMixin, viewsets.ModelViewSet):
    queryset = PersonnelRecord.objects.select_related("organization", "linked_candidate").all()
    serializer_class = PersonnelRecordSerializer
    permission_classes = [IsRegistryOperatorOrAdmin]
    filterset_fields = ["organization", "nationality", "is_active_officeholder", "is_public"]
    search_fields = ["full_name", "contact_email", "contact_phone", "bio_summary"]
    ordering_fields = ["full_name", "created_at", "updated_at"]

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
        if not is_platform_admin_actor(user):
            if requested_org is not None and not can_manage_registry(
                user,
                organization_id=requested_org.id,
                allow_membershipless_fallback=False,
            ):
                raise PermissionDenied("You cannot create personnel records for another organization.")
            active_org_id = get_request_active_organization_id(self.request)
            if requested_org is None and not active_org_id:
                raise PermissionDenied("Active organization context is required to create personnel records.")
            if requested_org is None and active_org_id:
                record = serializer.save(organization_id=active_org_id)
            else:
                record = serializer.save()
        else:
            record = serializer.save()
        log_event(
            request=self.request,
            action="create",
            entity_type="PersonnelRecord",
            entity_id=str(record.id),
            changes={
                "event": PERSONNEL_RECORD_CREATED_EVENT,
                "organization_id": str(record.organization_id or ""),
                "full_name": record.full_name,
                "is_public": record.is_public,
                "is_active_officeholder": record.is_active_officeholder,
            },
        )

    def perform_update(self, serializer):
        instance = serializer.instance
        user = self.request.user
        if not is_platform_admin_actor(user) and not can_manage_registry_record(
            user,
            instance,
            allow_membershipless_fallback=False,
        ):
            raise PermissionDenied("You cannot update personnel records outside your organization scope.")
        requested_org = serializer.validated_data.get("organization")
        if (
            not is_platform_admin_actor(user)
            and requested_org is not None
            and not can_manage_registry(
                user,
                organization_id=requested_org.id,
                allow_membershipless_fallback=False,
            )
        ):
            raise PermissionDenied("You cannot move this personnel record to another organization.")

        changed_fields = list(serializer.validated_data.keys())
        before = {field: getattr(instance, field, None) for field in changed_fields}
        save_kwargs = {}
        if (
            not is_platform_admin_actor(user)
            and instance.organization_id is None
            and "organization" not in serializer.validated_data
        ):
            active_org_id = get_request_active_organization_id(self.request)
            if active_org_id:
                save_kwargs["organization_id"] = active_org_id
        record = serializer.save(**save_kwargs)
        after = {field: getattr(record, field, None) for field in changed_fields}
        log_event(
            request=self.request,
            action="update",
            entity_type="PersonnelRecord",
            entity_id=str(record.id),
            changes={
                "event": PERSONNEL_RECORD_UPDATED_EVENT,
                "organization_id": str(record.organization_id or ""),
                "changed_fields": changed_fields,
                "before": before,
                "after": after,
            },
        )

    def perform_destroy(self, instance):
        user = self.request.user
        if not is_platform_admin_actor(user) and not can_manage_registry_record(
            user,
            instance,
            allow_membershipless_fallback=False,
        ):
            raise PermissionDenied("You cannot delete personnel records outside your organization scope.")
        snapshot = {
            "full_name": instance.full_name,
            "is_public": instance.is_public,
            "is_active_officeholder": instance.is_active_officeholder,
            "organization_id": str(instance.organization_id) if instance.organization_id else "",
        }
        entity_id = str(instance.id)
        super().perform_destroy(instance)
        log_event(
            request=self.request,
            action="delete",
            entity_type="PersonnelRecord",
            entity_id=entity_id,
            changes={
                "event": PERSONNEL_RECORD_DELETED_EVENT,
                "organization_id": str(snapshot.get("organization_id") or ""),
                "snapshot": snapshot,
            },
        )

    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny], url_path="officeholders")
    def officeholders(self, request):
        queryset = PersonnelRecord.objects.select_related("organization", "linked_candidate").filter(
            is_active_officeholder=True,
            is_public=True,
        )
        queryset = self.filter_queryset(queryset)
        serializer = PublicPersonnelRecordSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], permission_classes=[IsRegistryOperatorOrAdmin], url_path="link-candidate")
    def link_candidate(self, request, pk=None):
        personnel = self.get_object()
        if not is_platform_admin_actor(request.user) and not can_manage_registry_record(
            request.user,
            personnel,
            allow_membershipless_fallback=False,
        ):
            raise PermissionDenied("You cannot link candidates for personnel outside your organization scope.")
        candidate_id = request.data.get("candidate_id")
        if not candidate_id:
            return Response({"error": "candidate_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        candidate = Candidate.objects.filter(id=candidate_id).first()
        if candidate is None:
            return Response({"error": "Candidate not found."}, status=status.HTTP_404_NOT_FOUND)

        personnel.linked_candidate = candidate
        personnel.save(update_fields=["linked_candidate", "updated_at"])
        log_event(
            request=self.request,
            action="update",
            entity_type="PersonnelRecord",
            entity_id=str(personnel.id),
            changes={
                "event": PERSONNEL_LINKED_CANDIDATE_EVENT,
                "organization_id": str(personnel.organization_id or ""),
                "linked_candidate_id": str(candidate.id),
                "linked_candidate_email": candidate.email,
            },
        )
        serializer = self.get_serializer(personnel)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], permission_classes=[permissions.IsAuthenticated], url_path="appointment-history")
    def appointment_history(self, request, pk=None):
        personnel = self.get_object()
        rows = personnel.appointment_records.select_related("position").order_by("-created_at")
        if not can_view_internal_record(
            request.user,
            organization_id=getattr(personnel, "organization_id", None),
        ):
            rows = rows.filter(is_public=True)
        data = [
            {
                "id": row.id,
                "status": row.status,
                "position": row.position.title,
                "nomination_date": row.nomination_date,
                "appointment_date": row.appointment_date,
                "is_public": row.is_public,
            }
            for row in rows
        ]
        return Response(data)
