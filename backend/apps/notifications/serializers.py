from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for user notification records."""

    notification_type_display = serializers.CharField(
        source="get_notification_type_display",
        read_only=True,
    )
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )
    priority_display = serializers.CharField(
        source="get_priority_display",
        read_only=True,
    )
    recipient_email = serializers.EmailField(source="recipient.email", read_only=True)
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "recipient",
            "recipient_email",
            "template",
            "related_case",
            "related_interview",
            "subject",
            "message",
            "notification_type",
            "notification_type_display",
            "status",
            "status_display",
            "priority",
            "priority_display",
            "email_to",
            "email_cc",
            "metadata",
            "sent_at",
            "read_at",
            "failed_at",
            "failure_reason",
            "retry_count",
            "is_read",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "recipient",
            "recipient_email",
            "template",
            "related_case",
            "related_interview",
            "subject",
            "message",
            "notification_type",
            "status",
            "priority",
            "email_to",
            "email_cc",
            "metadata",
            "sent_at",
            "read_at",
            "failed_at",
            "failure_reason",
            "retry_count",
            "created_at",
        ]

    def get_is_read(self, obj) -> bool:
        return obj.status == "read"


class NotificationMarkReadSerializer(serializers.Serializer):
    """Payload for bulk mark-as-read action."""

    notification_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
    )
    mark_all = serializers.BooleanField(default=False)
