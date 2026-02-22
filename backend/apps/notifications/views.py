from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone

from .models import Notification
from .serializers import NotificationSerializer, NotificationMarkReadSerializer


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoints for notifications
    
    list: GET /api/notifications/
    retrieve: GET /api/notifications/{id}/
    mark_as_read: POST /api/notifications/mark-as-read/
    mark_all_as_read: POST /api/notifications/mark-all-as-read/
    unread_count: GET /api/notifications/unread-count/
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()

        user = self.request.user
        queryset = Notification.objects.filter(recipient=user).order_by("-created_at")

        status_value = self.request.query_params.get("status")
        if status_value:
            queryset = queryset.filter(status=status_value)

        notification_type = self.request.query_params.get("type")
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)

        priority = self.request.query_params.get("priority")
        if priority:
            queryset = queryset.filter(priority=priority)

        return queryset

    @action(detail=False, methods=["post"])
    def mark_as_read(self, request):
        """
        Mark specific notifications as read
        POST /api/notifications/mark-as-read/
        Body: {"notification_ids": [1, 2, 3]}
        """
        serializer = NotificationMarkReadSerializer(data=request.data)

        if serializer.is_valid():
            mark_all = serializer.validated_data.get("mark_all", False)
            notification_ids = serializer.validated_data.get("notification_ids", [])

            if mark_all:
                count = self.get_queryset().exclude(status="read").update(
                    status="read",
                    read_at=timezone.now(),
                )
                return Response({"message": f"{count} notifications marked as read"})

            if notification_ids:
                notifications = self.get_queryset().filter(id__in=notification_ids)
                notifications.update(
                    status="read",
                    read_at=timezone.now(),
                )

                return Response(
                    {"message": f"{notifications.count()} notifications marked as read"}
                )

            return Response(
                {"error": "No notification IDs provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"])
    def mark_all_as_read(self, request):
        """
        Mark all notifications as read
        POST /api/notifications/mark-all-as-read/
        """
        notifications = self.get_queryset().exclude(status="read")
        count = notifications.update(
            status="read",
            read_at=timezone.now(),
        )

        return Response({"message": f"{count} notifications marked as read"})

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        """
        Get count of unread notifications
        GET /api/notifications/unread-count/
        """
        count = self.get_queryset().exclude(status="read").count()

        return Response({"unread_count": count})

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        """
        Mark single notification as read
        POST /api/notifications/{id}/mark-read/
        """
        notification = self.get_object()
        notification.mark_read()

        return Response(
            {
                "message": "Notification marked as read",
                "notification": NotificationSerializer(notification).data,
            }
        )

    @action(detail=True, methods=["delete"])
    def archive(self, request, pk=None):
        """
        Delete (archive) a notification for the current user.

        DELETE /api/notifications/{id}/archive/
        """
        notification = self.get_object()
        notification.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
