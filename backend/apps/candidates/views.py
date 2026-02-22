from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Candidate, CandidateEnrollment
from .serializers import CandidateEnrollmentSerializer, CandidateSerializer


class CandidateViewSet(viewsets.ModelViewSet):
    serializer_class = CandidateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Candidate.objects.none()
        user = self.request.user
        queryset = Candidate.objects.all()

        if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False) or getattr(user, "user_type", None) == "admin":
            return queryset.order_by("-created_at")
        if getattr(user, "user_type", None) == "hr_manager":
            return queryset.filter(enrollments__campaign__initiated_by=user).distinct().order_by("-created_at")
        return Candidate.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        if getattr(user, "user_type", None) not in {"admin", "hr_manager"} and not getattr(user, "is_staff", False):
            raise PermissionDenied("Only HR managers/admins can create candidates.")
        serializer.save()


class CandidateEnrollmentViewSet(viewsets.ModelViewSet):
    serializer_class = CandidateEnrollmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return CandidateEnrollment.objects.none()
        user = self.request.user
        queryset = CandidateEnrollment.objects.select_related("campaign", "candidate", "decision_by").all()
        campaign_id = self.request.query_params.get("campaign")
        status_value = self.request.query_params.get("status")

        if not (getattr(user, "is_staff", False) or getattr(user, "is_superuser", False) or getattr(user, "user_type", None) == "admin"):
            if getattr(user, "user_type", None) == "hr_manager":
                queryset = queryset.filter(campaign__initiated_by=user)
            else:
                queryset = queryset.none()

        if campaign_id:
            queryset = queryset.filter(campaign_id=campaign_id)
        if status_value:
            queryset = queryset.filter(status=status_value)

        return queryset.order_by("-created_at")

    def perform_create(self, serializer):
        user = self.request.user
        campaign = serializer.validated_data["campaign"]
        if not (getattr(user, "is_staff", False) or getattr(user, "is_superuser", False) or getattr(user, "user_type", None) == "admin"):
            if getattr(user, "user_type", None) != "hr_manager":
                raise PermissionDenied("Only HR managers/admins can create enrollments.")
            if campaign.initiated_by_id != user.id:
                raise PermissionDenied("You cannot create enrollments for another manager's campaign.")
        now = timezone.now()
        serializer.save(invited_at=now)

    @action(detail=True, methods=["post"], url_path="mark-complete")
    def mark_complete(self, request, pk=None):
        enrollment = self.get_object()
        enrollment.status = "completed"
        enrollment.completed_at = timezone.now()
        enrollment.save(update_fields=["status", "completed_at", "updated_at"])

        return Response(self.get_serializer(enrollment).data, status=status.HTTP_200_OK)
