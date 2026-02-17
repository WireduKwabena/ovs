from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.candidates.models import CandidateEnrollment

from .models import Invitation
from .serializers import AcceptInvitationSerializer, InvitationCreateSerializer, InvitationSerializer
from .tasks import send_invitation_task


class InvitationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Invitation.objects.select_related("enrollment__campaign", "enrollment__candidate").all()

        campaign_id = self.request.query_params.get("campaign")
        enrollment_id = self.request.query_params.get("enrollment")
        status_value = self.request.query_params.get("status")

        if campaign_id:
            queryset = queryset.filter(enrollment__campaign_id=campaign_id)
        if enrollment_id:
            queryset = queryset.filter(enrollment_id=enrollment_id)
        if status_value:
            queryset = queryset.filter(status=status_value)

        return queryset.order_by("-created_at")

    def get_serializer_class(self):
        if self.action == "create":
            return InvitationCreateSerializer
        return InvitationSerializer

    def perform_create(self, serializer):
        invitation = serializer.save(created_by=self.request.user)
        send_invitation_task.delay(invitation.id)

        enrollment = invitation.enrollment
        if enrollment.status == "invited" and not enrollment.invited_at:
            enrollment.invited_at = timezone.now()
            enrollment.save(update_fields=["invited_at", "updated_at"])

    @action(detail=True, methods=["post"], url_path="send")
    def send_now(self, request, pk=None):
        invitation = self.get_object()
        send_invitation_task.delay(invitation.id)
        return Response({"message": "Invitation queued for sending."}, status=status.HTTP_202_ACCEPTED)


class AcceptInvitationAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AcceptInvitationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data["token"]
        try:
            invitation = Invitation.objects.select_related("enrollment__candidate", "enrollment__campaign").get(token=token)
        except Invitation.DoesNotExist:
            return Response({"error": "Invalid invitation token."}, status=status.HTTP_404_NOT_FOUND)

        if invitation.is_expired:
            if invitation.status != "expired":
                invitation.status = "expired"
                invitation.save(update_fields=["status", "updated_at"])
            return Response({"error": "Invitation has expired."}, status=status.HTTP_400_BAD_REQUEST)

        invitation.status = "accepted"
        invitation.accepted_at = timezone.now()
        invitation.save(update_fields=["status", "accepted_at", "updated_at"])

        enrollment = invitation.enrollment
        if enrollment.status == "invited":
            enrollment.status = "registered"
            enrollment.registered_at = timezone.now()
            enrollment.save(update_fields=["status", "registered_at", "updated_at"])

        return Response(
            {
                "message": "Invitation accepted.",
                "campaign": invitation.enrollment.campaign.name,
                "candidate_email": invitation.enrollment.candidate.email,
                "enrollment_status": enrollment.status,
            },
            status=status.HTTP_200_OK,
        )
