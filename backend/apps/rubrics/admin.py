from django.contrib import admin

from .models import (
    CriteriaOverride,
    RubricCriteria,
    RubricEvaluation,
    VettingDecisionOverride,
    VettingDecisionRecommendation,
    VettingRubric,
)


@admin.register(VettingRubric)
class VettingRubricAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "rubric_type",
        "passing_score",
        "auto_approve_threshold",
        "auto_reject_threshold",
        "is_active",
        "is_default",
        "created_by",
        "created_at",
    )
    list_filter = ("rubric_type", "is_active", "is_default", "created_at")
    search_fields = ("name", "description")
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("created_by",)


@admin.register(RubricCriteria)
class RubricCriteriaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "rubric",
        "name",
        "criteria_type",
        "scoring_method",
        "weight",
        "is_mandatory",
        "display_order",
    )
    list_filter = ("criteria_type", "scoring_method", "is_mandatory")
    search_fields = ("rubric__name", "name", "description")
    list_select_related = ("rubric",)


@admin.register(RubricEvaluation)
class RubricEvaluationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "case",
        "rubric",
        "status",
        "total_weighted_score",
        "final_decision",
        "requires_manual_review",
        "evaluated_at",
        "created_at",
    )
    list_filter = ("status", "final_decision", "requires_manual_review", "created_at")
    search_fields = ("case__case_id", "rubric__name", "evaluation_summary")
    readonly_fields = ("created_at", "updated_at", "evaluated_at")
    list_select_related = ("case", "rubric", "evaluated_by")


@admin.register(CriteriaOverride)
class CriteriaOverrideAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "evaluation",
        "criteria",
        "original_score",
        "overridden_score",
        "overridden_by",
        "created_at",
    )
    list_filter = ("created_at",)
    search_fields = ("evaluation__case__case_id", "criteria__name", "justification")
    readonly_fields = ("created_at",)
    list_select_related = ("evaluation", "criteria", "overridden_by")


@admin.register(VettingDecisionRecommendation)
class VettingDecisionRecommendationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "case",
        "rubric_evaluation",
        "recommendation_status",
        "advisory_only",
        "engine_version",
        "is_latest",
        "generated_by",
        "created_at",
    )
    list_filter = ("recommendation_status", "advisory_only", "is_latest", "created_at")
    search_fields = ("case__case_id", "rubric_evaluation__id")
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("case", "rubric_evaluation", "generated_by")


@admin.register(VettingDecisionOverride)
class VettingDecisionOverrideAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "recommendation",
        "previous_recommendation_status",
        "overridden_recommendation_status",
        "overridden_by",
        "created_at",
    )
    list_filter = ("overridden_recommendation_status", "created_at")
    search_fields = ("recommendation__case__case_id", "rationale")
    readonly_fields = ("created_at",)
    list_select_related = ("recommendation", "overridden_by")
