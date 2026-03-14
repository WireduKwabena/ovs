from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

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
    GOVERNMENT_POSITION_CREATED_EVENT,
    GOVERNMENT_POSITION_DELETED_EVENT,
    GOVERNMENT_POSITION_UPDATED_EVENT,
)
try:
    from apps.audit.events import log_event
except Exception:  # pragma: no cover - audit app may be optional in some setups
    def log_event(**kwargs):  # type: ignore
        return False

from .models import GovernmentPosition
from .serializers import GovernmentPositionSerializer, PublicGovernmentPositionSerializer


class GovernmentPositionViewSet(BlockPlatformAdminOrgWorkflowMixin, viewsets.ModelViewSet):
    queryset = GovernmentPosition.objects.select_related("organization", "current_holder", "rubric").all()
    serializer_class = GovernmentPositionSerializer
    permission_classes = [IsRegistryOperatorOrAdmin]
    filterset_fields = ["organization", "branch", "institution", "is_vacant", "is_public", "confirmation_required"]
    search_fields = ["title", "institution", "appointment_authority", "constitutional_basis"]
    ordering_fields = ["title", "institution", "created_at", "updated_at"]

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
                raise PermissionDenied("You cannot create position records for another organization.")
            active_org_id = get_request_active_organization_id(self.request)
            if requested_org is None and not active_org_id:
                raise PermissionDenied("Active organization context is required to create position records.")
            if requested_org is None and active_org_id:
                position = serializer.save(organization_id=active_org_id)
            else:
                position = serializer.save()
        else:
            position = serializer.save()
        log_event(
            request=self.request,
            action="create",
            entity_type="GovernmentPosition",
            entity_id=str(position.id),
            changes={
                "event": GOVERNMENT_POSITION_CREATED_EVENT,
                "organization_id": str(position.organization_id or ""),
                "title": position.title,
                "branch": position.branch,
                "institution": position.institution,
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
            raise PermissionDenied("You cannot update position records outside your organization scope.")
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
            raise PermissionDenied("You cannot move this position record to another organization.")

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
        position = serializer.save(**save_kwargs)
        after = {field: getattr(position, field, None) for field in changed_fields}
        log_event(
            request=self.request,
            action="update",
            entity_type="GovernmentPosition",
            entity_id=str(position.id),
            changes={
                "event": GOVERNMENT_POSITION_UPDATED_EVENT,
                "organization_id": str(position.organization_id or ""),
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
            raise PermissionDenied("You cannot delete position records outside your organization scope.")
        snapshot = {
            "title": instance.title,
            "branch": instance.branch,
            "institution": instance.institution,
            "appointment_authority": instance.appointment_authority,
            "organization_id": str(instance.organization_id) if instance.organization_id else "",
        }
        entity_id = str(instance.id)
        super().perform_destroy(instance)
        log_event(
            request=self.request,
            action="delete",
            entity_type="GovernmentPosition",
            entity_id=entity_id,
            changes={
                "event": GOVERNMENT_POSITION_DELETED_EVENT,
                "organization_id": str(snapshot.get("organization_id") or ""),
                "snapshot": snapshot,
            },
        )

    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny], url_path="public")
    def public_positions(self, request):
        queryset = GovernmentPosition.objects.select_related("organization", "current_holder", "rubric").filter(is_public=True)
        queryset = self.filter_queryset(queryset)
        serializer = PublicGovernmentPositionSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny], url_path="vacant")
    def vacant_positions(self, request):
        queryset = GovernmentPosition.objects.select_related("organization", "current_holder", "rubric").filter(
            is_vacant=True,
            is_public=True,
        )
        queryset = self.filter_queryset(queryset)
        serializer = PublicGovernmentPositionSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], permission_classes=[permissions.IsAuthenticated], url_path="appointment-history")
    def appointment_history(self, request, pk=None):
        position = self.get_object()
        rows = position.appointment_records.select_related("nominee").order_by("-created_at")
        if not can_view_internal_record(
            request.user,
            organization_id=getattr(position, "organization_id", None),
        ):
            rows = rows.filter(is_public=True)
        data = [
            {
                "id": row.id,
                "status": row.status,
                "nominee": row.nominee.full_name,
                "nomination_date": row.nomination_date,
                "appointment_date": row.appointment_date,
                "is_public": row.is_public,
            }
            for row in rows
        ]
        return Response(data)
