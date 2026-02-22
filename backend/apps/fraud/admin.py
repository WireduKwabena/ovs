from django.contrib import admin

from .models import ConsistencyCheckResult, FraudDetectionResult


@admin.register(FraudDetectionResult)
class FraudDetectionResultAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "application",
        "is_fraud",
        "fraud_probability",
        "anomaly_score",
        "risk_level",
        "recommendation",
        "detected_at",
    )
    list_filter = ("is_fraud", "risk_level", "recommendation", "detected_at")
    search_fields = ("application__case_id", "application__applicant__email")
    readonly_fields = ("id", "detected_at")
    list_select_related = ("application",)


@admin.register(ConsistencyCheckResult)
class ConsistencyCheckResultAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "application",
        "overall_consistent",
        "overall_score",
        "recommendation",
        "checked_at",
    )
    list_filter = ("overall_consistent", "checked_at")
    search_fields = ("application__case_id", "application__applicant__email", "recommendation")
    readonly_fields = ("id", "checked_at")
    list_select_related = ("application",)
