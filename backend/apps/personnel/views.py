from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.candidates.models import Candidate
from apps.core.permissions import IsHRManagerOrAdmin

from .models import PersonnelRecord
from .serializers import PersonnelRecordSerializer, PublicPersonnelRecordSerializer


class PersonnelRecordViewSet(viewsets.ModelViewSet):
    queryset = PersonnelRecord.objects.select_related("linked_candidate").all()
    serializer_class = PersonnelRecordSerializer
    permission_classes = [IsHRManagerOrAdmin]
    filterset_fields = ["nationality", "is_active_officeholder", "is_public"]
    search_fields = ["full_name", "contact_email", "contact_phone", "bio_summary"]
    ordering_fields = ["full_name", "created_at", "updated_at"]

    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny], url_path="officeholders")
    def officeholders(self, request):
        queryset = self.filter_queryset(
            self.get_queryset().filter(is_active_officeholder=True, is_public=True)
        )
        serializer = PublicPersonnelRecordSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], permission_classes=[IsHRManagerOrAdmin], url_path="link-candidate")
    def link_candidate(self, request, pk=None):
        personnel = self.get_object()
        candidate_id = request.data.get("candidate_id")
        if not candidate_id:
            return Response({"error": "candidate_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        candidate = Candidate.objects.filter(id=candidate_id).first()
        if candidate is None:
            return Response({"error": "Candidate not found."}, status=status.HTTP_404_NOT_FOUND)

        personnel.linked_candidate = candidate
        personnel.save(update_fields=["linked_candidate", "updated_at"])
        serializer = self.get_serializer(personnel)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], permission_classes=[permissions.IsAuthenticated], url_path="appointment-history")
    def appointment_history(self, request, pk=None):
        personnel = self.get_object()
        rows = personnel.appointment_records.select_related("position").order_by("-created_at")
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
