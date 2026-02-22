from datetime import timedelta

from django.db.models import Max
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.candidates.models import Candidate, CandidateEnrollment
from apps.invitations.models import Invitation
from apps.invitations.tasks import send_invitation_task

from .models import VettingCampaign
from .serializers import CampaignRubricVersionSerializer, VettingCampaignSerializer


class VettingCampaignViewSet(viewsets.ModelViewSet):
    serializer_class = VettingCampaignSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return VettingCampaign.objects.none()
        user = self.request.user
        if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False) or getattr(user, "user_type", None) == "admin":
            return VettingCampaign.objects.all().order_by("-created_at")
        return VettingCampaign.objects.filter(initiated_by=user).order_by("-created_at")

    def perform_create(self, serializer):
        user = self.request.user
        if getattr(user, "user_type", None) not in {"admin", "hr_manager"} and not getattr(user, "is_staff", False):
            raise PermissionDenied("Only HR managers/admins can create campaigns.")
        serializer.save(initiated_by=self.request.user)

    @action(detail=True, methods=["post"], url_path="rubrics/versions")
    def add_rubric_version(self, request, pk=None):
        campaign = self.get_object()
        next_version = (campaign.rubric_versions.aggregate(max_v=Max("version"))["max_v"] or 0) + 1

        serializer = CampaignRubricVersionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(campaign=campaign, version=next_version, created_by=request.user)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="dashboard")
    def dashboard(self, request, pk=None):
        campaign = self.get_object()
        enrollments = CandidateEnrollment.objects.filter(campaign=campaign)

        data = {
            "total_candidates": enrollments.count(),
            "invited": enrollments.filter(status="invited").count(),
            "registered": enrollments.filter(status="registered").count(),
            "in_progress": enrollments.filter(status="in_progress").count(),
            "completed": enrollments.filter(status="completed").count(),
            "reviewed": enrollments.filter(status="reviewed").count(),
            "approved": enrollments.filter(status="approved").count(),
            "rejected": enrollments.filter(status="rejected").count(),
            "escalated": enrollments.filter(status="escalated").count(),
        }
        return Response(data)

    @action(detail=True, methods=["post"], url_path="candidates/import")
    def import_candidates(self, request, pk=None):
        campaign = self.get_object()
        candidates_data = request.data.get("candidates", [])
        send_invites = bool(request.data.get("send_invites", False))

        if not isinstance(candidates_data, list) or not candidates_data:
            return Response(
                {"error": "Payload must include a non-empty 'candidates' list."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created_candidates = 0
        created_enrollments = 0
        created_invitations = 0
        errors = []

        for row in candidates_data:
            email = (row.get("email") or "").strip().lower()
            first_name = (row.get("first_name") or "").strip()
            last_name = (row.get("last_name") or "").strip()
            phone = (row.get("phone_number") or "").strip()
            channel = (row.get("preferred_channel") or "email").strip().lower()

            if not email or not first_name:
                errors.append({"email": email or None, "error": "email and first_name are required"})
                continue

            candidate, candidate_created = Candidate.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "phone_number": phone,
                    "preferred_channel": "sms" if channel == "sms" else "email",
                },
            )
            if candidate_created:
                created_candidates += 1
            else:
                updated = False
                if first_name and candidate.first_name != first_name:
                    candidate.first_name = first_name
                    updated = True
                if last_name and candidate.last_name != last_name:
                    candidate.last_name = last_name
                    updated = True
                if phone and candidate.phone_number != phone:
                    candidate.phone_number = phone
                    updated = True
                if channel in {"email", "sms"} and candidate.preferred_channel != channel:
                    candidate.preferred_channel = channel
                    updated = True
                if updated:
                    candidate.save()

            enrollment, enrollment_created = CandidateEnrollment.objects.get_or_create(
                campaign=campaign,
                candidate=candidate,
                defaults={
                    "status": "invited",
                    "invited_at": timezone.now(),
                },
            )
            if enrollment_created:
                created_enrollments += 1

            if send_invites:
                invite_channel = "sms" if channel == "sms" else "email"
                send_to = candidate.phone_number if invite_channel == "sms" else candidate.email
                if not send_to:
                    errors.append({"email": candidate.email, "error": "missing contact channel for invite"})
                    continue

                invitation = Invitation.objects.create(
                    enrollment=enrollment,
                    channel=invite_channel,
                    send_to=send_to,
                    expires_at=timezone.now() + timedelta(hours=72),
                    created_by=request.user,
                )
                created_invitations += 1
                send_invitation_task.delay(invitation.id)

        return Response(
            {
                "campaign_id": campaign.id,
                "created_candidates": created_candidates,
                "created_enrollments": created_enrollments,
                "created_invitations": created_invitations,
                "errors": errors,
            },
            status=status.HTTP_200_OK,
        )
