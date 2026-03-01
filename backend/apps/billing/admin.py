from django.contrib import admin

from .models import BillingSubscription, BillingWebhookEvent


@admin.register(BillingSubscription)
class BillingSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "provider",
        "session_id",
        "plan_id",
        "billing_cycle",
        "status",
        "payment_status",
        "amount_usd",
        "updated_at",
    )
    list_filter = ("provider", "status", "billing_cycle", "payment_status")
    search_fields = ("session_id", "payment_intent_id", "plan_id", "plan_name", "reference")
    readonly_fields = ("created_at", "updated_at")


@admin.register(BillingWebhookEvent)
class BillingWebhookEventAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "provider",
        "event_id",
        "event_type",
        "processing_status",
        "created_at",
        "processed_at",
    )
    list_filter = ("provider", "processing_status", "event_type")
    search_fields = ("event_id", "event_type", "processing_error")
    readonly_fields = ("created_at", "processed_at")