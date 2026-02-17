from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Candidate, CandidateEnrollment
from .serializers import CandidateEnrollmentSerializer, CandidateSerializer


class CandidateViewSet(viewsets.ModelViewSet):
    queryset = Candidate.objects.all().order_by("-created_at")
    serializer_class = CandidateSerializer
    permission_classes = [IsAuthenticated]


class CandidateEnrollmentViewSet(viewsets.ModelViewSet):
    serializer_class = CandidateEnrollmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = CandidateEnrollment.objects.select_related("campaign", "candidate", "decision_by").all()
        campaign_id = self.request.query_params.get("campaign")
        status_value = self.request.query_params.get("status")

        if campaign_id:
            queryset = queryset.filter(campaign_id=campaign_id)
        if status_value:
            queryset = queryset.filter(status=status_value)

        return queryset.order_by("-created_at")

    def perform_create(self, serializer):
        now = timezone.now()
        serializer.save(invited_at=now)

    @action(detail=True, methods=["post"], url_path="mark-complete")
    def mark_complete(self, request, pk=None):
        enrollment = self.get_object()
        enrollment.status = "completed"
        enrollment.completed_at = timezone.now()
        enrollment.save(update_fields=["status", "completed_at", "updated_at"])

        return Response(self.get_serializer(enrollment).data, status=status.HTTP_200_OK)
