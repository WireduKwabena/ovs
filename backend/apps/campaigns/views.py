from datetime import timedelta

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import IntegrityError
from django.db.models import Max
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.billing.quotas import enforce_candidate_quota, resolve_case_organization_id
from apps.candidates.models import Candidate, CandidateEnrollment
from apps.core.authz import CAPABILITY_REGISTRY_MANAGE, has_capability
from apps.core.permissions import (
    is_platform_admin_user,
)
from apps.core.policies.registry_policy import can_manage_registry
from apps.invitations.models import Invitation
from apps.invitations.tasks import send_invitation_task

from .models import CampaignRubricVersion, VettingCampaign
from .permissions import IsInternalWorkflowOperator
from .serializers import CampaignRubricVersionSerializer, VettingCampaignSerializer


def _project_new_enrollment_count(campaign, candidates_data) -> int:
    """Estimate how many enrollment rows would be newly created by bulk import."""
    normalized_rows = []
    for row in candidates_data:
        if not isinstance(row, dict):
            continue
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
    permission_classes = [IsInternalWorkflowOperator]

    def _require_registry_manage(self, *, detail: str):
        user = self.request.user
        if is_platform_admin_user(user):
            return
        if can_manage_registry(user, allow_membershipless_fallback=False):
            return
        raise PermissionDenied(detail)

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return VettingCampaign.objects.none()
        user = self.request.user
        if not getattr(user, "is_authenticated", False):
            return VettingCampaign.objects.none()
        if is_platform_admin_user(user):
            return VettingCampaign.objects.all().order_by("-created_at")
        # Registry managers without an active org membership are scoped to their
        # own campaigns only.  Users with an org membership (or without registry
        # capability) retain access to all campaigns so that write-operations can
        # still produce the correct 403 via _require_registry_manage.
        if has_capability(user, CAPABILITY_REGISTRY_MANAGE):
            from apps.governance.models import OrganizationMembership
            has_membership = OrganizationMembership.objects.filter(
                user=user, is_active=True
            ).exists()
            if not has_membership:
                return VettingCampaign.objects.filter(
                    initiated_by=user
                ).order_by("-created_at")
        return VettingCampaign.objects.all().order_by("-created_at")

    def perform_create(self, serializer):
        self._require_registry_manage(detail="You do not have permission to create campaigns.")
        serializer.save(initiated_by=self.request.user)

    def perform_update(self, serializer):
        self._require_registry_manage(detail="You do not have permission to update campaigns.")
        serializer.save()

    def perform_destroy(self, instance):
        self._require_registry_manage(detail="You do not have permission to delete campaigns.")
        super().perform_destroy(instance)

    @action(detail=True, methods=["get", "post"], url_path="rubrics/versions")
    def add_rubric_version(self, request, pk=None):
        campaign = self.get_object()
        if request.method.lower() == "get":
            versions = campaign.rubric_versions.all().order_by("-version", "-created_at")
            serializer = CampaignRubricVersionSerializer(versions, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        self._require_registry_manage(detail="You do not have permission to manage campaign rubric versions.")

        next_version = (campaign.rubric_versions.aggregate(max_v=Max("version"))["max_v"] or 0) + 1

        serializer = CampaignRubricVersionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(campaign=campaign, version=next_version, created_by=request.user)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="rubrics/versions/activate")
    def activate_rubric_version(self, request, pk=None):
        campaign = self.get_object()
        self._require_registry_manage(detail="You do not have permission to activate campaign rubric versions.")
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
        self._require_registry_manage(detail="You do not have permission to import candidates for this campaign.")
        candidates_data = request.data.get("candidates", [])
        send_invites = bool(request.data.get("send_invites", False))

        if not isinstance(candidates_data, list) or not candidates_data:
            return Response(
                {"error": "Payload must include a non-empty 'candidates' list."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        is_admin = bool(is_platform_admin_user(user))
        if not is_admin:
            projected_new_enrollments = _project_new_enrollment_count(campaign, candidates_data)
            if projected_new_enrollments > 0:
                from django.db import connection as _conn
                org_id = str(getattr(getattr(_conn, "tenant", None), "id", "") or "").strip() or None
                enforce_candidate_quota(
                    user=user,
                    additional=projected_new_enrollments,
                    organization_id=org_id,
                )

        created_candidates = 0
        created_enrollments = 0
        created_invitations = 0
        errors = []

        for row_index, row in enumerate(candidates_data, start=1):
            if not isinstance(row, dict):
                errors.append({"row": row_index, "error": "each candidate entry must be an object"})
                continue

            email = (row.get("email") or "").strip().lower()
            first_name = (row.get("first_name") or "").strip()
            last_name = (row.get("last_name") or "").strip()
            phone = (row.get("phone_number") or "").strip()
            channel = (row.get("preferred_channel") or "email").strip().lower()

            if not email or not first_name:
                errors.append({"row": row_index, "email": email or None, "error": "email and first_name are required"})
                continue

            try:
                validate_email(email)
            except DjangoValidationError:
                errors.append({"row": row_index, "email": email, "error": "email is invalid"})
                continue

            if channel not in {"email", "sms"}:
                errors.append({"row": row_index, "email": email, "error": "preferred_channel must be 'email' or 'sms'"})
                continue

            try:
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
                    if candidate.preferred_channel != channel:
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
                        errors.append({"row": row_index, "email": candidate.email, "error": "missing contact channel for invite"})
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
            except IntegrityError:
                errors.append({"row": row_index, "email": email, "error": "candidate row could not be imported due to a data conflict"})
            except Exception as exc:
                errors.append({"row": row_index, "email": email or None, "error": f"candidate row import failed: {exc}"})

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
