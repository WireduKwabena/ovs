from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.audit.events import log_event
from apps.billing.quotas import (
    VETTING_OPERATION_DOCUMENT_VERIFICATION,
    VETTING_OPERATION_SOCIAL_PROFILE_CHECK,
    enforce_candidate_quota,
    enforce_vetting_operation_quota,
    resolve_case_organization_id,
)
from apps.core.permissions import (
    can_access_organization_id,
    get_request_active_organization_id,
    get_user_allowed_organization_ids,
    is_platform_admin_user,
    scope_queryset_to_user_organizations,
)
from apps.invitations.permissions import IsAuthenticatedOrCandidateAccessSession

from .models import Document, VettingCase
from .serializers import DocumentSerializer, DocumentUploadSerializer, VettingCaseSerializer
from .social_checks import run_case_social_profile_check
from .tasks import verify_document_async


def _candidate_enrollment_id(request) -> int | None:
    candidate_session = getattr(request, "candidate_access_session", None)
    return getattr(candidate_session, "enrollment_id", None)


def _audit_social_recheck(request, case: VettingCase, outcome: dict) -> None:
    """Persist manual social re-check activity to audit trail when available."""
    status_label = "ok" if outcome.get("success") else ("skipped" if outcome.get("reason") == "no_profiles" else "error")

    result_payload = outcome.get("result") if isinstance(outcome.get("result"), dict) else {}
    summary = {
        "profiles_checked": int(result_payload.get("profiles_checked", 0) or 0),
        "overall_score": float(result_payload.get("overall_score", 0.0) or 0.0),
        "risk_level": str(result_payload.get("risk_level", "") or ""),
        "recommendation": str(result_payload.get("recommendation", "") or ""),
    }

    changes = {
        "event": "social_profile_recheck",
        "status": status_label,
        "case_code": str(case.case_id),
        "reason": outcome.get("reason"),
        "record_id": outcome.get("record_id"),
        "result_summary": summary,
    }

    log_event(
        request=request,
        action="other",
        entity_type="VettingCase",
        entity_id=str(case.id),
        changes=changes,
    )

class VettingCaseViewSet(viewsets.ModelViewSet):
    serializer_class = VettingCaseSerializer
    permission_classes = [IsAuthenticatedOrCandidateAccessSession]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return VettingCase.objects.none()
        queryset = VettingCase.objects.select_related(
            "organization",
            "applicant",
            "assigned_to",
            "candidate_enrollment",
            "candidate_enrollment__candidate",
        ).prefetch_related("documents")

        enrollment_id = _candidate_enrollment_id(self.request)
        if enrollment_id:
            return queryset.filter(candidate_enrollment_id=enrollment_id).order_by("-created_at")

        user = self.request.user
        scope = str(self.request.query_params.get("scope", "") or "").strip().lower()
        if not getattr(user, "is_authenticated", False):
            return VettingCase.objects.none()
        if is_platform_admin_user(user):
            return queryset.order_by("-created_at")

        if getattr(user, "user_type", None) == "hr_manager":
            membership_org_ids = get_user_allowed_organization_ids(user)
            if membership_org_ids:
                queryset = scope_queryset_to_user_organizations(
                    queryset,
                    request=self.request,
                    organization_field="organization_id",
                )
            if getattr(user, "user_type", None) == "hr_manager" and scope in {"assigned", "mine", "my"}:
                return queryset.filter(assigned_to=user).order_by("-created_at")
            return queryset.order_by("-created_at")
        return queryset.filter(applicant=user).order_by("-created_at")

    def get_object(self):
        """
        Support lookup by numeric PK and human-readable ``case_id``.

        This keeps existing frontend routes that pass ``case_id`` compatible with
        router-generated detail endpoints.
        """
        queryset = self.filter_queryset(self.get_queryset())
        lookup_value = self.kwargs.get(self.lookup_url_kwarg or self.lookup_field)
        if lookup_value is None:
            return super().get_object()

        obj = None
        if str(lookup_value).isdigit():
            obj = queryset.filter(pk=lookup_value).first()

        if obj is None:
            obj = queryset.filter(case_id=str(lookup_value)).first()

        if obj is None:
            obj = get_object_or_404(queryset, pk=lookup_value)

        self.check_object_permissions(self.request, obj)
        return obj

    def perform_create(self, serializer):
        if _candidate_enrollment_id(self.request):
            raise PermissionDenied("Candidates cannot create vetting cases directly.")
        user = self.request.user
        if getattr(user, "user_type", None) == "applicant":
            serializer.save(applicant=user)
        else:
            applicant = serializer.validated_data.get("applicant")
            candidate_enrollment = serializer.validated_data.get("candidate_enrollment")
            requested_org = serializer.validated_data.get("organization")
            if applicant is None:
                raise ValidationError({"applicant": "This field is required for non-applicant creators."})

            is_admin = is_platform_admin_user(user)
            is_hr_manager = getattr(user, "user_type", None) == "hr_manager"

            resolved_org_id = None
            if requested_org is not None:
                resolved_org_id = str(requested_org.id)
            elif candidate_enrollment is not None:
                resolved_org_id = str(getattr(candidate_enrollment.campaign, "organization_id", "") or "") or None
            else:
                resolved_org_id = get_request_active_organization_id(self.request)

            if not is_admin:
                if requested_org is not None and not can_access_organization_id(user, requested_org.id):
                    raise PermissionDenied("You cannot create vetting cases for another organization.")
                if resolved_org_id and not can_access_organization_id(user, resolved_org_id):
                    raise PermissionDenied("You cannot create vetting cases for another organization.")

            if is_hr_manager and candidate_enrollment is not None:
                campaign_owner_id = getattr(candidate_enrollment.campaign, "initiated_by_id", None)
                campaign_org_id = getattr(candidate_enrollment.campaign, "organization_id", None)
                if campaign_owner_id != user.id and not (campaign_org_id and can_access_organization_id(user, campaign_org_id)):
                    raise PermissionDenied("You cannot create cases for enrollments outside your campaigns.")

            # Legacy/manual case creation path can bypass enrollment quota checks,
            # so enforce subscription plan quota here when no enrollment linkage exists.
            if is_hr_manager and candidate_enrollment is None:
                enforce_candidate_quota(
                    user=user,
                    additional=1,
                    organization_id=resolved_org_id,
                )

            if resolved_org_id:
                serializer.save(organization_id=resolved_org_id)
            else:
                serializer.save()

    def perform_update(self, serializer):
        instance = serializer.instance
        user = self.request.user
        if not is_platform_admin_user(user) and not can_access_organization_id(user, instance.organization_id):
            raise PermissionDenied("You cannot update vetting cases outside your organization scope.")

        requested_org = serializer.validated_data.get("organization")
        if not is_platform_admin_user(user) and requested_org is not None and not can_access_organization_id(
            user, requested_org.id
        ):
            raise PermissionDenied("You cannot move this vetting case to another organization.")

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
        if not is_platform_admin_user(user) and not can_access_organization_id(user, instance.organization_id):
            raise PermissionDenied("You cannot delete vetting cases outside your organization scope.")
        super().perform_destroy(instance)

    @action(detail=True, methods=["post"], url_path="upload-document")
    def upload_document(self, request, pk=None):
        case = self.get_object()
        resolved_org_id = resolve_case_organization_id(case)
        quota_actor = None
        if not resolved_org_id and getattr(request.user, "is_authenticated", False):
            quota_actor = request.user
        enforce_vetting_operation_quota(
            operation=VETTING_OPERATION_DOCUMENT_VERIFICATION,
            user=quota_actor,
            organization_id=resolved_org_id,
            additional=1,
        )
        payload = request.data.copy()
        if "file" not in payload and "document" in request.FILES:
            payload["file"] = request.FILES["document"]

        serializer = DocumentUploadSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        requested_document_type = serializer.validated_data["document_type"]

        enrollment = case.candidate_enrollment
        required_document_types: list[str] = []
        if enrollment and enrollment.campaign_id:
            settings_json = enrollment.campaign.settings_json if isinstance(enrollment.campaign.settings_json, dict) else {}
            raw_required_types = settings_json.get("required_document_types")
            if isinstance(raw_required_types, list):
                allowed_values = {choice[0] for choice in Document.DOCUMENT_TYPE_CHOICES}
                required_document_types = []
                for item in raw_required_types:
                    normalized = str(item)
                    if normalized in allowed_values and normalized not in required_document_types:
                        required_document_types.append(normalized)

        if required_document_types and requested_document_type not in required_document_types:
            raise ValidationError(
                {
                    "document_type": (
                        f"'{requested_document_type}' is not required for this campaign. "
                        "Upload one of the campaign-required document types."
                    ),
                    "required_document_types": required_document_types,
                }
            )

        file = serializer.validated_data["file"]
        document = Document.objects.create(
            case=case,
            document_type=requested_document_type,
            file=file,
            original_filename=file.name,
            file_size=file.size,
            mime_type=getattr(file, "content_type", "") or "application/octet-stream",
            status="queued",
        )

        case.documents_uploaded = True
        if case.status in {"pending", "document_upload"}:
            case.status = "document_analysis"
        case.save(update_fields=["documents_uploaded", "status", "updated_at"])

        if enrollment and enrollment.status in {"invited", "registered"}:
            enrollment.status = "in_progress"
            if not enrollment.registered_at:
                enrollment.registered_at = timezone.now()
            enrollment.save(update_fields=["status", "registered_at", "updated_at"])

        verify_document_async.delay(document.id)

        output = DocumentSerializer(document, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="verification-status")
    def verification_status(self, request, pk=None):
        case = self.get_object()
        documents = case.documents.select_related("verification_result").all()

        document_rows = []
        for document in documents:
            result = getattr(document, "verification_result", None)
            document_rows.append(
                {
                    "id": document.id,
                    "document_type": document.document_type,
                    "status": document.status,
                    "uploaded_at": document.uploaded_at,
                    "processed_at": document.processed_at,
                    "authenticity_score": getattr(result, "authenticity_score", None),
                    "fraud_risk_score": getattr(result, "fraud_risk_score", None),
                    "fraud_prediction": getattr(result, "fraud_prediction", None),
                }
            )

        unresolved_flags = case.interrogation_flags.exclude(status__in=["resolved", "dismissed"])
        evaluation = getattr(case, "rubric_evaluation", None)
        recommendation = None
        if evaluation is not None:
            recommendation = (
                evaluation.decision_recommendations.filter(is_latest=True)
                .order_by("-created_at")
                .first()
            )
        try:
            social_result = case.social_profile_result
        except Exception:
            social_result = None

        return Response(
            {
                "case_id": case.case_id,
                "status": case.status,
                "documents_total": documents.count(),
                "documents_processed": documents.filter(status__in=["verified", "flagged", "failed"]).count(),
                "documents": document_rows,
                "unresolved_flags": unresolved_flags.count(),
                "requires_manual_review": case.requires_manual_review,
                "scores": {
                    "overall_score": case.overall_score,
                    "document_authenticity_score": case.document_authenticity_score,
                    "consistency_score": case.consistency_score,
                    "fraud_risk_score": case.fraud_risk_score,
                    "interview_score": case.interview_score,
                },
                "rubric_evaluation": (
                    {
                        "id": evaluation.id,
                        "rubric_id": evaluation.rubric_id,
                        "total_weighted_score": evaluation.total_weighted_score,
                        "passes_threshold": evaluation.passes_threshold,
                        "final_decision": evaluation.final_decision,
                        "decision_recommendation": (
                            {
                                "id": recommendation.id,
                                "recommendation_status": recommendation.recommendation_status,
                                "advisory_only": recommendation.advisory_only,
                                "blocking_issues_count": len(recommendation.blocking_issues or []),
                                "warnings_count": len(recommendation.warnings or []),
                            }
                            if recommendation
                            else None
                        ),
                    }
                    if evaluation
                    else None
                ),
                "social_profile_result": (
                    {
                        "id": str(social_result.id),
                        "consent_provided": social_result.consent_provided,
                        "profiles_checked": social_result.profiles_checked,
                        "overall_score": social_result.overall_score,
                        "risk_level": social_result.risk_level,
                        "recommendation": social_result.recommendation,
                        "automated_decision_allowed": social_result.automated_decision_allowed,
                        "decision_constraints": social_result.decision_constraints,
                        "profiles": social_result.profiles,
                        "checked_at": social_result.checked_at,
                        "updated_at": social_result.updated_at,
                    }
                    if social_result
                    else None
                ),
            }
        )

    @action(detail=True, methods=["post"], url_path="recheck-social-profiles")
    def recheck_social_profiles(self, request, pk=None):
        case = self.get_object()

        if _candidate_enrollment_id(request):
            raise PermissionDenied("Candidate session cannot trigger social profile re-check.")

        user = request.user
        if not (
            getattr(user, "is_staff", False)
            or getattr(user, "is_superuser", False)
            or getattr(user, "user_type", None) in {"admin", "hr_manager"}
        ):
            raise PermissionDenied("Only HR managers/admins can trigger social profile re-check.")

        try:
            existing_social_result = case.social_profile_result
        except Exception:
            existing_social_result = None

        resolved_org_id = resolve_case_organization_id(case)
        quota_actor = None if resolved_org_id else user
        enforce_vetting_operation_quota(
            operation=VETTING_OPERATION_SOCIAL_PROFILE_CHECK,
            user=quota_actor,
            organization_id=resolved_org_id,
            additional=0 if existing_social_result is not None else 1,
        )

        outcome = run_case_social_profile_check(case, actor=user)
        _audit_social_recheck(request=request, case=case, outcome=outcome)
        if outcome.get("success"):
            return Response({"status": "ok", **outcome}, status=status.HTTP_200_OK)

        if outcome.get("reason") == "no_profiles":
            return Response({"status": "skipped", **outcome}, status=status.HTTP_200_OK)

        return Response({"status": "error", **outcome}, status=status.HTTP_400_BAD_REQUEST)


class DocumentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticatedOrCandidateAccessSession]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Document.objects.none()
        queryset = Document.objects.select_related("case", "verification_result", "case__applicant", "case__organization")

        case_id = self.request.query_params.get("case")
        status_value = self.request.query_params.get("status")
        if case_id:
            queryset = queryset.filter(case_id=case_id)
        if status_value:
            queryset = queryset.filter(status=status_value)

        enrollment_id = _candidate_enrollment_id(self.request)
        if enrollment_id:
            return queryset.filter(case__candidate_enrollment_id=enrollment_id).order_by("-uploaded_at")

        user = self.request.user
        if not getattr(user, "is_authenticated", False):
            return Document.objects.none()
        if is_platform_admin_user(user):
            return queryset.order_by("-uploaded_at")
        if getattr(user, "user_type", None) == "hr_manager":
            membership_org_ids = get_user_allowed_organization_ids(user)
            if membership_org_ids:
                queryset = scope_queryset_to_user_organizations(
                    queryset,
                    request=self.request,
                    organization_field="case__organization_id",
                )
            return queryset.order_by("-uploaded_at")
        return queryset.filter(Q(case__applicant=user) | Q(case__assigned_to=user)).order_by("-uploaded_at")

