from datetime import timedelta

from django.db.models import Max
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.billing.quotas import enforce_candidate_quota
from apps.candidates.models import Candidate, CandidateEnrollment
from apps.core.permissions import (
    can_access_organization_id,
    get_request_active_organization_id,
    get_user_allowed_organization_ids,
    is_platform_admin_user,
    scope_internal_queryset_to_tenant,
)
from apps.invitations.models import Invitation
from apps.invitations.tasks import send_invitation_task

from .models import CampaignRubricVersion, VettingCampaign
from .permissions import IsHRManagerOrAdmin
from .serializers import CampaignRubricVersionSerializer, VettingCampaignSerializer


def _project_new_enrollment_count(campaign, candidates_data) -> int:
    """Estimate how many enrollment rows would be newly created by bulk import."""
    normalized_rows = []
    for row in candidates_data:
        email = (row.get("email") or "").strip().lower()
        first_name = (row.get("first_name") or "").strip()
        if not email or not first_name:
            continue
        normalized_rows.append(email)

    if not normalized_rows:
        return 0

    existing_emails = {
        value.strip().lower()
        for value in CandidateEnrollment.objects.filter(
            campaign=campaign,
            candidate__email__in=set(normalized_rows),
        ).values_list("candidate__email", flat=True)
        if value
    }

    projected = set()
    for email in normalized_rows:
        if email in existing_emails or email in projected:
            continue
        projected.add(email)
    return len(projected)


class VettingCampaignViewSet(viewsets.ModelViewSet):
    serializer_class = VettingCampaignSerializer
    permission_classes = [IsHRManagerOrAdmin]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return VettingCampaign.objects.none()
        user = self.request.user
        queryset = VettingCampaign.objects.all()
        if is_platform_admin_user(user):
            return VettingCampaign.objects.all().order_by("-created_at")

        membership_org_ids = get_user_allowed_organization_ids(user)
        if membership_org_ids:
            queryset = scope_internal_queryset_to_tenant(
                queryset,
                request=self.request,
                organization_field="organization_id",
            )
            return queryset.order_by("-created_at")
        return VettingCampaign.objects.filter(initiated_by=user).order_by("-created_at")

    def perform_create(self, serializer):
        user = self.request.user
        if getattr(user, "user_type", None) not in {"admin", "hr_manager"} and not getattr(user, "is_staff", False):
            raise PermissionDenied("Only HR managers/admins can create campaigns.")
        requested_org = serializer.validated_data.get("organization")
        if not is_platform_admin_user(user):
            if requested_org is not None and not can_access_organization_id(
                user,
                requested_org.id,
                allow_membershipless_fallback=False,
            ):
                raise PermissionDenied("You cannot create campaigns for another organization.")
            active_org_id = get_request_active_organization_id(self.request)
            if requested_org is None and not active_org_id:
                raise PermissionDenied("Active organization context is required to create campaigns.")
            if requested_org is None and active_org_id:
                serializer.save(initiated_by=self.request.user, organization_id=active_org_id)
                return
        serializer.save(initiated_by=self.request.user)

    def perform_update(self, serializer):
        instance = serializer.instance
        user = self.request.user
        if not is_platform_admin_user(user) and not can_access_organization_id(
            user,
            instance.organization_id,
            allow_membershipless_fallback=False,
        ):
            raise PermissionDenied("You cannot update campaigns outside your organization scope.")
        requested_org = serializer.validated_data.get("organization")
        if not is_platform_admin_user(user) and requested_org is not None and not can_access_organization_id(
            user,
            requested_org.id,
            allow_membershipless_fallback=False,
        ):
            raise PermissionDenied("You cannot move this campaign to another organization.")
        save_kwargs = {}
        if (
            not is_platform_admin_user(user)
            and instance.organization_id is None
            and "organization" not in serializer.validated_data
        ):
            active_org_id = get_request_active_organization_id(self.request)
            if active_org_id:
                save_kwargs["organization_id"] = active_org_id
        serializer.save(**save_kwargs)

    def perform_destroy(self, instance):
        user = self.request.user
        if not is_platform_admin_user(user) and not can_access_organization_id(
            user,
            instance.organization_id,
            allow_membershipless_fallback=False,
        ):
            raise PermissionDenied("You cannot delete campaigns outside your organization scope.")
        super().perform_destroy(instance)

    @action(detail=True, methods=["get", "post"], url_path="rubrics/versions")
    def add_rubric_version(self, request, pk=None):
        campaign = self.get_object()
        if request.method.lower() == "get":
            versions = campaign.rubric_versions.all().order_by("-version", "-created_at")
            serializer = CampaignRubricVersionSerializer(versions, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        next_version = (campaign.rubric_versions.aggregate(max_v=Max("version"))["max_v"] or 0) + 1

        serializer = CampaignRubricVersionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(campaign=campaign, version=next_version, created_by=request.user)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="rubrics/versions/activate")
    def activate_rubric_version(self, request, pk=None):
        campaign = self.get_object()
        version_id = request.data.get("version_id")
        if not version_id:
            return Response({"error": "version_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            version = CampaignRubricVersion.objects.get(id=version_id, campaign=campaign)
        except CampaignRubricVersion.DoesNotExist:
            return Response({"error": "Rubric version not found"}, status=status.HTTP_404_NOT_FOUND)

        version.is_active = True
        version.save()
        serializer = CampaignRubricVersionSerializer(version)
        return Response(serializer.data, status=status.HTTP_200_OK)

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

        user = request.user
        is_admin = bool(
            getattr(user, "is_staff", False)
            or getattr(user, "is_superuser", False)
            or getattr(user, "user_type", None) == "admin"
        )
        if not is_admin:
            projected_new_enrollments = _project_new_enrollment_count(campaign, candidates_data)
            if projected_new_enrollments > 0:
                enforce_candidate_quota(
                    user=user,
                    additional=projected_new_enrollments,
                    organization_id=(
                        str(getattr(campaign, "organization_id", "") or "").strip()
                        or str(get_request_active_organization_id(self.request) or "").strip()
                        or None
                    ),
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
