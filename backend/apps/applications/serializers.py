from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.candidates.models import CandidateEnrollment

try:
    from drf_spectacular.utils import extend_schema_field
except ModuleNotFoundError:  # pragma: no cover - optional in some setups
    def extend_schema_field(*args, **kwargs):
        def decorator(func):
            return func

        return decorator

from .models import ConsistencyCheck, Document, InterrogationFlag, VerificationResult, VettingCase

User = get_user_model()


class VerificationResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = VerificationResult
        fields = [
            "id",
            "document",
            "ocr_text",
            "ocr_confidence",
            "ocr_language",
            "authenticity_score",
            "authenticity_confidence",
            "is_authentic",
            "metadata_check_passed",
            "visual_check_passed",
            "tampering_detected",
            "fraud_risk_score",
            "fraud_prediction",
            "fraud_indicators",
            "detailed_results",
            "ocr_model_version",
            "authenticity_model_version",
            "fraud_model_version",
            "created_at",
            "processing_time_seconds",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "processing_time_seconds",
        ]


class DocumentSerializer(serializers.ModelSerializer):
    verification_result = VerificationResultSerializer(read_only=True)
    document_type_display = serializers.CharField(source="get_document_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    file_url = serializers.CharField(read_only=True)

    class Meta:
        model = Document
        fields = [
            "id",
            "case",
            "document_type",
            "document_type_display",
            "file",
            "original_filename",
            "file_size",
            "mime_type",
            "status",
            "status_display",
            "ocr_completed",
            "authenticity_check_completed",
            "fraud_check_completed",
            "processing_error",
            "retry_count",
            "extracted_text",
            "extracted_data",
            "uploaded_at",
            "processed_at",
            "file_url",
            "verification_result",
        ]
        read_only_fields = [
            "id",
            "original_filename",
            "file_size",
            "mime_type",
            "status",
            "ocr_completed",
            "authenticity_check_completed",
            "fraud_check_completed",
            "processing_error",
            "retry_count",
            "uploaded_at",
            "processed_at",
            "file_url",
            "verification_result",
        ]


class ConsistencyCheckSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsistencyCheck
        fields = [
            "id",
            "case",
            "field_name",
            "documents_compared",
            "is_consistent",
            "severity",
            "discrepancy_description",
            "conflicting_values",
            "resolved",
            "resolution_notes",
            "resolved_by",
            "resolved_at",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "resolved_at"]


class InterrogationFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterrogationFlag
        fields = [
            "id",
            "case",
            "related_documents",
            "related_consistency_check",
            "flag_type",
            "severity",
            "status",
            "title",
            "description",
            "data_point",
            "evidence",
            "suggested_questions",
            "resolution_summary",
            "resolution_confidence",
            "resolved_by",
            "created_at",
            "addressed_at",
            "resolved_at",
        ]
        read_only_fields = ["id", "created_at", "addressed_at", "resolved_at"]


class VettingCaseSerializer(serializers.ModelSerializer):
    applicant_email = serializers.EmailField(source="applicant.email", read_only=True)
    candidate_email = serializers.EmailField(source="candidate_enrollment.candidate.email", read_only=True)
    assigned_to_email = serializers.EmailField(source="assigned_to.email", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    priority_display = serializers.CharField(source="get_priority_display", read_only=True)
    documents = DocumentSerializer(many=True, read_only=True)
    applicant = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(user_type="applicant"),
        required=False,
    )
    candidate_enrollment = serializers.PrimaryKeyRelatedField(
        queryset=CandidateEnrollment.objects.select_related("candidate", "campaign"),
        required=False,
        allow_null=True,
    )
    rubric_evaluation = serializers.SerializerMethodField(read_only=True)
    social_profile_result = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = VettingCase
        fields = [
            "id",
            "case_id",
            "applicant",
            "applicant_email",
            "candidate_enrollment",
            "candidate_email",
            "assigned_to",
            "assigned_to_email",
            "position_applied",
            "department",
            "job_description",
            "status",
            "status_display",
            "priority",
            "priority_display",
            "overall_score",
            "document_authenticity_score",
            "consistency_score",
            "fraud_risk_score",
            "interview_score",
            "red_flags_count",
            "requires_manual_review",
            "notes",
            "internal_comments",
            "documents_uploaded",
            "documents_verified",
            "interview_completed",
            "final_decision",
            "decision_rationale",
            "decided_by",
            "decided_at",
            "created_at",
            "updated_at",
            "submitted_at",
            "completed_at",
            "expected_completion_date",
            "documents",
            "rubric_evaluation",
            "social_profile_result",
        ]
        read_only_fields = [
            "id",
            "case_id",
            "applicant_email",
            "candidate_email",
            "assigned_to_email",
            "status_display",
            "priority_display",
            "overall_score",
            "document_authenticity_score",
            "consistency_score",
            "fraud_risk_score",
            "interview_score",
            "red_flags_count",
            "created_at",
            "updated_at",
            "completed_at",
            "documents",
            "rubric_evaluation",
            "social_profile_result",
        ]

    @extend_schema_field(serializers.JSONField(allow_null=True))
    def get_rubric_evaluation(self, obj) -> dict[str, object] | None:
        evaluation = getattr(obj, "rubric_evaluation", None)
        if not evaluation:
            return None
        return {
            "id": evaluation.id,
            "rubric_id": evaluation.rubric_id,
            "total_weighted_score": evaluation.total_weighted_score,
            "passes_threshold": evaluation.passes_threshold,
            "final_decision": evaluation.final_decision,
            "requires_manual_review": evaluation.requires_manual_review,
        }

    @extend_schema_field(serializers.JSONField(allow_null=True))
    def get_social_profile_result(self, obj) -> dict[str, object] | None:
        try:
            social_result = obj.social_profile_result
        except Exception:
            social_result = None

        if not social_result:
            return None

        return {
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


class DocumentUploadSerializer(serializers.Serializer):
    document_type = serializers.ChoiceField(choices=Document.DOCUMENT_TYPE_CHOICES)
    file = serializers.FileField()
