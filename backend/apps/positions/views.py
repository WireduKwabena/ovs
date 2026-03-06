from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import IsHRManagerOrAdmin

from .models import GovernmentPosition
from .serializers import GovernmentPositionSerializer, PublicGovernmentPositionSerializer


class GovernmentPositionViewSet(viewsets.ModelViewSet):
    queryset = GovernmentPosition.objects.select_related("current_holder", "rubric").all()
    serializer_class = GovernmentPositionSerializer
    permission_classes = [IsHRManagerOrAdmin]
    filterset_fields = ["branch", "institution", "is_vacant", "is_public", "confirmation_required"]
    search_fields = ["title", "institution", "appointment_authority", "constitutional_basis"]
    ordering_fields = ["title", "institution", "created_at", "updated_at"]

    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny], url_path="public")
    def public_positions(self, request):
        queryset = self.filter_queryset(self.get_queryset().filter(is_public=True))
        serializer = PublicGovernmentPositionSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny], url_path="vacant")
    def vacant_positions(self, request):
        queryset = self.filter_queryset(self.get_queryset().filter(is_vacant=True, is_public=True))
        serializer = PublicGovernmentPositionSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], permission_classes=[permissions.IsAuthenticated], url_path="appointment-history")
    def appointment_history(self, request, pk=None):
        position = self.get_object()
        rows = position.appointment_records.select_related("nominee").order_by("-created_at")
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
