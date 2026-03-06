# backend/apps/audit/serializers.py

from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    """Serializer for audit logs"""
    user_name = serializers.SerializerMethodField()
    admin_user_name = serializers.SerializerMethodField()
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id', 'user', 'user_name', 'admin_user', 'admin_user_name',
            'action', 'action_display', 'entity_type', 'entity_id',
            'changes', 'ip_address', 'user_agent', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_user_name(self, obj) -> str | None:
        if not obj.user:
            return None
        return obj.user.get_full_name() if hasattr(obj.user, "get_full_name") else obj.user.email
    
    def get_admin_user_name(self, obj) -> str | None:
        if not obj.admin_user:
            return None
        return (
            obj.admin_user.get_full_name()
            if hasattr(obj.admin_user, "get_full_name")
            else obj.admin_user.email
        )


class AuditEventCatalogItemSerializer(serializers.Serializer):
    """Schema for one audit event key contract item."""

    key = serializers.CharField()
    entity_type = serializers.CharField()
    action = serializers.CharField()
    description = serializers.CharField()


class AuditEventCatalogSerializer(serializers.Serializer):
    """Schema for audit event catalog response."""

    count = serializers.IntegerField()
    results = AuditEventCatalogItemSerializer(many=True)


class AuditByEntityErrorSerializer(serializers.Serializer):
    """Schema for by_entity validation errors."""

    error = serializers.CharField()


class AuditByUserErrorSerializer(serializers.Serializer):
    """Schema for by_user validation errors."""

    error = serializers.CharField()


class AuditActionDistributionSerializer(serializers.Serializer):
    """Schema for action distribution entries."""

    action = serializers.CharField()
    count = serializers.IntegerField()


class AuditEntityDistributionSerializer(serializers.Serializer):
    """Schema for entity distribution entries."""

    entity_type = serializers.CharField()
    count = serializers.IntegerField()


class AuditStatisticsSerializer(serializers.Serializer):
    """Schema for audit statistics endpoint."""

    total_logs = serializers.IntegerField()
    action_distribution = AuditActionDistributionSerializer(many=True)
    entity_distribution = AuditEntityDistributionSerializer(many=True)
