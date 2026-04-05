from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.core.permissions import (
    BlockPlatformAdminOrgWorkflowMixin,
    IsRegistryOperatorOrAdmin,
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
    queryset = GovernmentPosition.objects.select_related("current_holder", "rubric").all()
    serializer_class = GovernmentPositionSerializer
    permission_classes = [IsRegistryOperatorOrAdmin]
    filterset_fields = ["branch", "institution", "is_vacant", "is_public", "confirmation_required"]
    search_fields = ["title", "institution", "appointment_authority", "constitutional_basis"]
    ordering_fields = ["title", "institution", "created_at", "updated_at"]

    def get_queryset(self):
        return super().get_queryset()

    def perform_create(self, serializer):
        user = self.request.user
        if not is_platform_admin_actor(user):
            if not can_manage_registry(user, allow_membershipless_fallback=False):
                raise PermissionDenied("You do not have permission to create position records.")
        position = serializer.save()
        log_event(
            request=self.request,
            action="create",
            entity_type="GovernmentPosition",
            entity_id=str(position.id),
            changes={
                "event": GOVERNMENT_POSITION_CREATED_EVENT,
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

        changed_fields = list(serializer.validated_data.keys())
        before = {field: getattr(instance, field, None) for field in changed_fields}
        position = serializer.save()
        after = {field: getattr(position, field, None) for field in changed_fields}
        log_event(
            request=self.request,
            action="update",
            entity_type="GovernmentPosition",
            entity_id=str(position.id),
            changes={
                "event": GOVERNMENT_POSITION_UPDATED_EVENT,
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
                "snapshot": snapshot,
            },
        )

    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny], url_path="public")
    def public_positions(self, request):
        queryset = GovernmentPosition.objects.select_related("current_holder", "rubric").filter(is_public=True)
        queryset = self.filter_queryset(queryset)
        serializer = PublicGovernmentPositionSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny], url_path="vacant")
    def vacant_positions(self, request):
        queryset = GovernmentPosition.objects.select_related("current_holder", "rubric").filter(
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
        if not can_view_internal_record(request.user):
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
