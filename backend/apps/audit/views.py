# backend/apps/audit/views.py

from django.db.models import Count, Q
from django_filters import rest_framework as django_filters
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from apps.core.authz import get_user_committee_ids, get_user_organization_ids
from apps.core.permissions import IsAuditReaderOrAdmin, is_admin_user

from .contracts import GOVERNMENT_AUDIT_EVENT_CATALOG
from .models import AuditLog
from .serializers import (
    AuditByEntityErrorSerializer,
    AuditByUserErrorSerializer,
    AuditEventCatalogSerializer,
    AuditLogSerializer,
    AuditStatisticsSerializer,
)


class AuditLogFilter(django_filters.FilterSet):
    changes__event = django_filters.CharFilter(field_name="changes__event", lookup_expr="exact")

    class Meta:
        model = AuditLog
        fields = ["action", "entity_type", "entity_id"]


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoints for audit logs (read-only)
    
    list: GET /api/audit/logs/
    retrieve: GET /api/audit/logs/{id}/
    by_entity: GET /api/audit/logs/by_entity/?entity_type=VettingCase&entity_id=1
    by_user: GET /api/audit/logs/by_user/?user_id=<uuid>
    """
    queryset = AuditLog.objects.select_related("user", "admin_user").all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuditReaderOrAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = AuditLogFilter
    search_fields = ['entity_type', 'changes']
    ordering_fields = ['created_at']
    ordering = ['-created_at']

    @staticmethod
    def _legacy_org_scoped_entity_ids(
        *,
        allowed_org_ids: set[str],
        entity_types: set[str],
    ) -> dict[str, list[str]]:
        if not allowed_org_ids:
            return {}

        from apps.applications.models import VettingCase
        from apps.appointments.models import AppointmentRecord
        from apps.campaigns.models import VettingCampaign
        from apps.personnel.models import PersonnelRecord
        from apps.positions.models import GovernmentPosition

        mappings = {
            "AppointmentRecord": AppointmentRecord,
            "GovernmentPosition": GovernmentPosition,
            "PersonnelRecord": PersonnelRecord,
            "VettingCampaign": VettingCampaign,
            "VettingCase": VettingCase,
        }
        scoped: dict[str, list[str]] = {}
        for entity_type in entity_types:
            model = mappings.get(entity_type)
            if model is None:
                continue
            values = (
                model.objects.filter(
                    Q(organization_id__in=list(allowed_org_ids)) | Q(organization_id__isnull=True)
                )
                .values_list("id", flat=True)
            )
            scoped[entity_type] = [str(value) for value in values]
        return scoped

    def _scoped_queryset_for_non_admin(self, queryset):
        user = self.request.user
        allowed_org_ids = set(get_user_organization_ids(user))
        allowed_committee_ids = set(get_user_committee_ids(user))

        scope_q = Q(user_id=user.id) | Q(admin_user_id=user.id)
        if allowed_org_ids:
            scope_q |= Q(scope_organization_id__in=list(allowed_org_ids))
            scope_q |= Q(scope_organization_id="", changes__organization_id__in=list(allowed_org_ids))
        if allowed_committee_ids:
            scope_q |= Q(scope_committee_id__in=list(allowed_committee_ids))
            scope_q |= Q(scope_committee_id="", changes__committee_id__in=list(allowed_committee_ids))

        legacy_missing_context_q = (
            Q(scope_organization_id="")
            & Q(scope_committee_id="")
            & Q(changes__organization_id__isnull=True)
            & Q(changes__committee_id__isnull=True)
        )

        # Legacy compatibility for old events that predate org/committee payload keys.
        if allowed_org_ids:
            legacy_entity_types = set(
                queryset.filter(legacy_missing_context_q).values_list("entity_type", flat=True).distinct()
            )
            legacy_entity_ids = self._legacy_org_scoped_entity_ids(
                allowed_org_ids=allowed_org_ids,
                entity_types=legacy_entity_types,
            )
            for entity_type, entity_ids in legacy_entity_ids.items():
                if not entity_ids:
                    continue
                scope_q |= (
                    Q(entity_type=entity_type, entity_id__in=entity_ids)
                    & legacy_missing_context_q
                )
        return queryset.filter(scope_q).distinct()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return AuditLog.objects.none()
        queryset = super().get_queryset()
        user = getattr(self.request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return AuditLog.objects.none()
        if is_admin_user(user):
            return queryset
        return self._scoped_queryset_for_non_admin(queryset)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="changes__event",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter audit logs by changes.event key (exact match).",
            )
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="entity_type",
                type=str,
                location=OpenApiParameter.QUERY,
                required=True,
                description="Entity type to filter by (e.g. AppointmentRecord).",
            ),
            OpenApiParameter(
                name="entity_id",
                type=str,
                location=OpenApiParameter.QUERY,
                required=True,
                description="Entity identifier to filter by.",
            ),
        ],
        responses={
            200: AuditLogSerializer(many=True),
            400: AuditByEntityErrorSerializer,
        },
    )
    @action(detail=False, methods=['get'])
    def by_entity(self, request):
        """
        Get audit logs for a specific entity
        GET /api/audit/logs/by-entity/?entity_type=VettingCase&entity_id=1
        """
        entity_type = request.query_params.get('entity_type')
        entity_id = request.query_params.get('entity_id')
        
        if not entity_type or not entity_id:
            return Response(
                {'error': 'entity_type and entity_id are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        logs = self.get_queryset().filter(
            entity_type=entity_type,
            entity_id=entity_id
        )
        
        serializer = self.get_serializer(logs, many=True)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="user_id",
                type=str,
                location=OpenApiParameter.QUERY,
                required=True,
                description="User UUID to filter by (matches user or admin_user actor fields).",
            ),
        ],
        responses={
            200: AuditLogSerializer(many=True),
            400: AuditByUserErrorSerializer,
        },
    )
    @action(detail=False, methods=["get"])
    def by_user(self, request):
        """Get audit logs for a specific acting user/admin_user UUID."""
        user_id = request.query_params.get("user_id")
        if not user_id:
            return Response(
                {"error": "user_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        logs = self.get_queryset().filter(Q(user_id=user_id) | Q(admin_user_id=user_id))
        serializer = self.get_serializer(logs, many=True)
        return Response(serializer.data)
    
    @extend_schema(responses={200: AuditLogSerializer(many=True)})
    @action(detail=False, methods=['get'])
    def recent_activity(self, request):
        """
        Get recent activity (last 50 logs)
        GET /api/audit/logs/recent-activity/
        """
        logs = self.get_queryset()[:50]
        serializer = self.get_serializer(logs, many=True)
        return Response(serializer.data)
    
    @extend_schema(responses={200: AuditStatisticsSerializer})
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get audit log statistics
        GET /api/audit/logs/statistics/
        """
        queryset = self.get_queryset()
        
        action_counts = queryset.values('action').annotate(
            count=Count('id')
        ).order_by('-count')
        
        entity_counts = queryset.values('entity_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        return Response({
            'total_logs': queryset.count(),
            'action_distribution': list(action_counts),
            'entity_distribution': list(entity_counts)
        })

    @extend_schema(responses={200: AuditEventCatalogSerializer})
    @action(detail=False, methods=["get"])
    def event_catalog(self, request):
        """Expose stable audit event keys for frontend filtering/labeling."""
        return Response(
            {
                "count": len(GOVERNMENT_AUDIT_EVENT_CATALOG),
                "results": GOVERNMENT_AUDIT_EVENT_CATALOG,
            }
        )
