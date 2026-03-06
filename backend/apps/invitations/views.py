from django.conf import settings
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.applications.models import VettingCase
from apps.interviews.models import InterviewSession

try:
    from drf_spectacular.types import OpenApiTypes
    from drf_spectacular.utils import extend_schema
except ModuleNotFoundError:  # pragma: no cover - optional in some setups
    class _OpenApiTypes:
        OBJECT = dict

    OpenApiTypes = _OpenApiTypes()

    def extend_schema(*args, **kwargs):
        def decorator(func):
            return func

        return decorator

from .permissions import HasCandidateAccessSession
from .models import Invitation
from .serializers import (
    AcceptInvitationSerializer,
    CandidateAccessConsumeSerializer,
    EmptySerializer,
    InvitationCreateSerializer,
    InvitationSerializer,
)
from .services import (
    CandidateAccessError,
    build_candidate_access_url,
    close_candidate_access_session,
    consume_candidate_access_token,
    issue_candidate_access_pass,
    touch_candidate_access_session,
)
from .tasks import send_invitation_task


class InvitationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Invitation.objects.none()
        user = self.request.user
        queryset = Invitation.objects.select_related("enrollment__campaign", "enrollment__candidate").all()

        if not (getattr(user, "is_staff", False) or getattr(user, "is_superuser", False) or getattr(user, "user_type", None) == "admin"):
            if getattr(user, "user_type", None) == "hr_manager":
                queryset = queryset.filter(enrollment__campaign__initiated_by=user)
            else:
                queryset = queryset.none()

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
        user = self.request.user
        enrollment = serializer.validated_data["enrollment"]
        if not (getattr(user, "is_staff", False) or getattr(user, "is_superuser", False) or getattr(user, "user_type", None) == "admin"):
            if getattr(user, "user_type", None) != "hr_manager":
                raise PermissionDenied("Only HR managers/admins can create invitations.")
            if enrollment.campaign.initiated_by_id != user.id:
                raise PermissionDenied("You cannot create invitations for another manager's campaign.")

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
    serializer_class = AcceptInvitationSerializer

    @extend_schema(
        request=AcceptInvitationSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
    )
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

        _, raw_access_token = issue_candidate_access_pass(
            enrollment=enrollment,
            invitation=invitation,
            pass_type="portal",
            issued_by=invitation.created_by,
            metadata={"issued_via": "accept_invitation"},
            revoke_existing=True,
        )
        access_url = build_candidate_access_url(raw_access_token)

        return Response(
            {
                "message": "Invitation accepted.",
                "campaign": invitation.enrollment.campaign.name,
                "candidate_email": invitation.enrollment.candidate.email,
                "enrollment_status": enrollment.status,
                "access_url": access_url,
            },
            status=status.HTTP_200_OK,
        )


def _candidate_context_payload(candidate_session):
    enrollment = candidate_session.enrollment
    candidate = enrollment.candidate
    campaign = enrollment.campaign
    return {
        "session_key": str(candidate_session.session_key),
        "session_expires_at": candidate_session.expires_at,
        "enrollment_id": enrollment.id,
        "enrollment_status": enrollment.status,
        "campaign": {
            "id": campaign.id,
            "name": campaign.name,
            "status": campaign.status,
        },
        "candidate": {
            "id": candidate.id,
            "first_name": candidate.first_name,
            "last_name": candidate.last_name,
            "email": candidate.email,
            "preferred_channel": candidate.preferred_channel,
        },
    }


class CandidateAccessConsumeAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = CandidateAccessConsumeSerializer

    @extend_schema(
        request=CandidateAccessConsumeSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
    )
    def post(self, request):
        serializer = CandidateAccessConsumeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            candidate_session, access_pass = consume_candidate_access_token(
                raw_token=serializer.validated_data["token"],
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                begin_vetting=serializer.validated_data.get("begin_vetting", True),
            )
        except CandidateAccessError as exc:
            code = status.HTTP_400_BAD_REQUEST
            if exc.code == "invalid":
                code = status.HTTP_404_NOT_FOUND
            return Response({"error": str(exc), "code": exc.code}, status=code)

        session_ttl_hours = int(getattr(settings, "CANDIDATE_ACCESS_SESSION_TTL_HOURS", 12))

        request.session.cycle_key()
        request.session["candidate_access_session_key"] = str(candidate_session.session_key)
        request.session.set_expiry(session_ttl_hours * 3600)

        payload = _candidate_context_payload(candidate_session)
        payload.update(
            {
                "pass_type": access_pass.pass_type,
                "remaining_uses": access_pass.remaining_uses,
                "message": "Candidate access granted.",
            }
        )
        return Response(payload, status=status.HTTP_200_OK)


class CandidateAccessContextAPIView(APIView):
    permission_classes = [HasCandidateAccessSession]

    @extend_schema(
        responses={
            200: OpenApiTypes.OBJECT,
            401: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
        },
    )
    def get(self, request):
        candidate_session = request.candidate_access_session
        touch_candidate_access_session(candidate_session)
        return Response(_candidate_context_payload(candidate_session), status=status.HTTP_200_OK)


class CandidateAccessResultsAPIView(APIView):
    permission_classes = [HasCandidateAccessSession]

    @extend_schema(
        responses={
            200: OpenApiTypes.OBJECT,
            401: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
        },
    )
    def get(self, request):
        candidate_session = request.candidate_access_session
        touch_candidate_access_session(candidate_session)

        enrollment = candidate_session.enrollment
        results_available_statuses = {"completed", "reviewed", "approved", "rejected", "escalated"}
        available = enrollment.status in results_available_statuses

        results_payload = {}
        metadata = enrollment.metadata or {}
        if isinstance(metadata, dict):
            results_payload = metadata.get("results") or metadata.get("result") or {}

        linked_case = VettingCase.objects.filter(candidate_enrollment_id=enrollment.id).order_by("-created_at").first()
        latest_interview = (
            InterviewSession.objects.filter(case=linked_case).order_by("-created_at").first() if linked_case else None
        )

        case_snapshot = None
        if linked_case:
            case_snapshot = {
                "id": linked_case.id,
                "case_id": linked_case.case_id,
                "status": linked_case.status,
                "final_decision": linked_case.final_decision,
                "overall_score": linked_case.overall_score,
                "document_authenticity_score": linked_case.document_authenticity_score,
                "consistency_score": linked_case.consistency_score,
                "fraud_risk_score": linked_case.fraud_risk_score,
                "interview_score": linked_case.interview_score,
            }
            if not results_payload:
                results_payload = {
                    "overall_score": linked_case.overall_score,
                    "document_authenticity_score": linked_case.document_authenticity_score,
                    "consistency_score": linked_case.consistency_score,
                    "fraud_risk_score": linked_case.fraud_risk_score,
                    "interview_score": linked_case.interview_score,
                }

        interview_snapshot = None
        if latest_interview:
            interview_snapshot = {
                "id": latest_interview.id,
                "session_id": latest_interview.session_id,
                "status": latest_interview.status,
                "overall_score": latest_interview.overall_score,
                "started_at": latest_interview.started_at,
                "completed_at": latest_interview.completed_at,
            }

        return Response(
            {
                "available": available,
                "enrollment_id": enrollment.id,
                "enrollment_status": enrollment.status,
                "decision": enrollment.status if enrollment.status in {"approved", "rejected", "escalated"} else None,
                "review_notes": enrollment.review_notes if available else "",
                "results": results_payload if available else {},
                "case": case_snapshot,
                "latest_interview": interview_snapshot,
            },
            status=status.HTTP_200_OK,
        )


class CandidateAccessLogoutAPIView(APIView):
    permission_classes = [HasCandidateAccessSession]
    serializer_class = EmptySerializer

    @extend_schema(
        responses={
            200: OpenApiTypes.OBJECT,
            401: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
        },
    )
    def post(self, request):
        candidate_session = request.candidate_access_session
        close_candidate_access_session(candidate_session, reason="logout")
        request.session.pop("candidate_access_session_key", None)
        return Response({"message": "Candidate session closed."}, status=status.HTTP_200_OK)
