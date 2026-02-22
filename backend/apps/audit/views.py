# backend/apps/audit/views.py

from django.db.models import Count
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoints for audit logs (read-only)
    
    list: GET /api/audit/logs/
    retrieve: GET /api/audit/logs/{id}/
    by_entity: GET /api/audit/logs/by-entity/?entity_type=VettingCase&entity_id=1
    by_user: GET /api/audit/logs/by-user/?user_id=1
    """
    queryset = AuditLog.objects.select_related("user", "admin_user").all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['action', 'entity_type', 'entity_id']
    search_fields = ['entity_type', 'changes']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return AuditLog.objects.none()
        
        queryset = super().get_queryset()
        user = self.request.user
        
        # Regular users can only see their own logs
        if not (
            getattr(user, "is_staff", False)
            or getattr(user, "is_superuser", False)
            or getattr(user, "user_type", None) in {"admin", "hr_manager"}
        ):
            queryset = queryset.filter(user=user)
        # Admins can see all logs
        
        return queryset
    
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
    
    @action(detail=False, methods=['get'])
    def recent_activity(self, request):
        """
        Get recent activity (last 50 logs)
        GET /api/audit/logs/recent-activity/
        """
        logs = self.get_queryset()[:50]
        serializer = self.get_serializer(logs, many=True)
        return Response(serializer.data)
    
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
