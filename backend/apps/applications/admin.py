from django.contrib import admin

from .models import (
    ConsistencyCheck,
    Document,
    ExternalVerificationResult,
    InterrogationFlag,
    VerificationRequest,
    VerificationResult,
    VerificationSource,
    VettingCase,
)


@admin.register(VettingCase)
class VettingCaseAdmin(admin.ModelAdmin):
    list_display = (
        "case_id",
        "applicant",
        "candidate_enrollment",
        "status",
        "priority",
        "overall_score",
        "requires_manual_review",
        "created_at",
    )
    list_filter = ("status", "priority", "requires_manual_review", "created_at")
    search_fields = ("case_id", "applicant__email", "position_applied", "department")
    readonly_fields = ("case_id", "created_at", "updated_at", "submitted_at", "completed_at")
    list_select_related = ("applicant", "assigned_to", "candidate_enrollment")


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "case", "document_type", "status", "ocr_completed", "uploaded_at")
    list_filter = ("document_type", "status", "ocr_completed", "uploaded_at")
    search_fields = ("case__case_id", "original_filename", "mime_type")
    readonly_fields = ("file_size", "original_filename", "uploaded_at", "processed_at")
    list_select_related = ("case",)


@admin.register(VerificationResult)
class VerificationResultAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "document",
        "authenticity_score",
        "fraud_risk_score",
        "is_authentic",
        "created_at",
    )
    list_filter = ("is_authentic", "fraud_prediction", "created_at")
    search_fields = ("document__case__case_id", "document__original_filename")
    readonly_fields = ("created_at",)
    list_select_related = ("document", "document__case")


@admin.register(ConsistencyCheck)
class ConsistencyCheckAdmin(admin.ModelAdmin):
    list_display = ("id", "case", "field_name", "is_consistent", "severity", "resolved", "created_at")
    list_filter = ("is_consistent", "severity", "resolved", "created_at")
    search_fields = ("case__case_id", "field_name", "discrepancy_description")
    readonly_fields = ("created_at",)
    filter_horizontal = ("documents_compared",)
    list_select_related = ("case", "resolved_by")


@admin.register(InterrogationFlag)
class InterrogationFlagAdmin(admin.ModelAdmin):
    list_display = ("id", "case", "flag_type", "severity", "status", "created_at", "resolved_at")
    list_filter = ("flag_type", "severity", "status", "created_at")
    search_fields = ("case__case_id", "title", "description", "data_point")
    readonly_fields = ("created_at", "addressed_at", "resolved_at")
    filter_horizontal = ("related_documents",)
    list_select_related = ("case", "related_consistency_check", "resolved_by")


@admin.register(VerificationSource)
class VerificationSourceAdmin(admin.ModelAdmin):
    list_display = ("key", "name", "source_category", "integration_mode", "is_active", "advisory_only")
    list_filter = ("source_category", "integration_mode", "is_active", "advisory_only")
    search_fields = ("key", "name", "description")
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("created_by",)


@admin.register(VerificationRequest)
class VerificationRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "case", "source", "status", "requested_by", "requested_at")
    list_filter = ("status", "source", "requested_at")
    search_fields = ("case__case_id", "source__key", "external_reference", "idempotency_key")
    readonly_fields = ("requested_at", "updated_at")
    list_select_related = ("case", "source", "requested_by")


@admin.register(ExternalVerificationResult)
class ExternalVerificationResultAdmin(admin.ModelAdmin):
    list_display = ("id", "case", "source", "result_status", "recommendation", "confidence_score", "received_at")
    list_filter = ("result_status", "recommendation", "source")
    search_fields = ("case__case_id", "source__key", "provider_reference")
    readonly_fields = ("received_at", "updated_at")
    list_select_related = ("case", "source", "verification_request")
