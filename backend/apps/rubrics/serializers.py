from rest_framework import serializers

from .models import CriteriaOverride, RubricCriteria, RubricEvaluation, VettingRubric


class RubricCriteriaSerializer(serializers.ModelSerializer):
    criteria_type_display = serializers.CharField(source="get_criteria_type_display", read_only=True)
    scoring_method_display = serializers.CharField(source="get_scoring_method_display", read_only=True)

    class Meta:
        model = RubricCriteria
        fields = [
            "id",
            "rubric",
            "name",
            "description",
            "criteria_type",
            "criteria_type_display",
            "scoring_method",
            "scoring_method_display",
            "weight",
            "minimum_score",
            "is_mandatory",
            "evaluation_guidelines",
            "display_order",
        ]
        read_only_fields = ["id"]


class VettingRubricSerializer(serializers.ModelSerializer):
    criteria = RubricCriteriaSerializer(many=True, read_only=True)
    rubric_type_display = serializers.CharField(source="get_rubric_type_display", read_only=True)
    total_weight = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = VettingRubric
        fields = [
            "id",
            "name",
            "description",
            "rubric_type",
            "rubric_type_display",
            "document_authenticity_weight",
            "consistency_weight",
            "fraud_detection_weight",
            "interview_weight",
            "manual_review_weight",
            "passing_score",
            "auto_approve_threshold",
            "auto_reject_threshold",
            "minimum_document_score",
            "maximum_fraud_score",
            "require_interview",
            "critical_flags_auto_fail",
            "max_unresolved_flags",
            "is_active",
            "is_default",
            "created_by",
            "created_at",
            "updated_at",
            "criteria",
            "total_weight",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at", "criteria", "total_weight"]

    def get_total_weight(self, obj) -> int:
        return (
            obj.document_authenticity_weight
            + obj.consistency_weight
            + obj.fraud_detection_weight
            + obj.interview_weight
            + obj.manual_review_weight
        )


class CriteriaOverrideSerializer(serializers.ModelSerializer):
    criteria_name = serializers.CharField(source="criteria.name", read_only=True)
    overridden_by_email = serializers.EmailField(source="overridden_by.email", read_only=True)

    class Meta:
        model = CriteriaOverride
        fields = [
            "id",
            "evaluation",
            "criteria",
            "criteria_name",
            "original_score",
            "overridden_score",
            "justification",
            "overridden_by",
            "overridden_by_email",
            "created_at",
        ]
        read_only_fields = ["id", "overridden_by", "overridden_by_email", "created_at"]


class RubricEvaluationSerializer(serializers.ModelSerializer):
    rubric_name = serializers.CharField(source="rubric.name", read_only=True)
    case_id = serializers.CharField(source="case.case_id", read_only=True)
    overrides = CriteriaOverrideSerializer(many=True, read_only=True)

    class Meta:
        model = RubricEvaluation
        fields = [
            "id",
            "case",
            "case_id",
            "rubric",
            "rubric_name",
            "status",
            "document_authenticity_score",
            "consistency_score",
            "fraud_risk_score",
            "interview_score",
            "manual_review_score",
            "weighted_document_score",
            "weighted_consistency_score",
            "weighted_fraud_score",
            "weighted_interview_score",
            "weighted_manual_score",
            "total_weighted_score",
            "passes_threshold",
            "final_decision",
            "critical_flags_present",
            "unresolved_flags_count",
            "requires_manual_review",
            "review_reasons",
            "criterion_scores",
            "evaluation_summary",
            "recommendations",
            "evaluated_at",
            "evaluated_by",
            "created_at",
            "updated_at",
            "overrides",
        ]
        read_only_fields = [
            "id",
            "weighted_document_score",
            "weighted_consistency_score",
            "weighted_fraud_score",
            "weighted_interview_score",
            "weighted_manual_score",
            "total_weighted_score",
            "passes_threshold",
            "final_decision",
            "requires_manual_review",
            "review_reasons",
            "evaluated_at",
            "created_at",
            "updated_at",
            "overrides",
        ]
