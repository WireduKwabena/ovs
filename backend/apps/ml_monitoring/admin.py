from django.contrib import admin

from .models import MLModelMetrics


@admin.register(MLModelMetrics)
class MLModelMetricsAdmin(admin.ModelAdmin):
    list_display = (
        "model_name",
        "model_version",
        "accuracy",
        "precision",
        "recall",
        "f1_score",
        "trained_at",
        "evaluated_at",
    )
    list_filter = ("model_name", "model_version", "evaluated_at")
    search_fields = ("model_name", "model_version")
    readonly_fields = ("id", "evaluated_at")
