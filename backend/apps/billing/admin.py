from django.contrib import admin

from .models import BillingSubscription, BillingWebhookEvent, OrganizationOnboardingToken


@admin.register(BillingSubscription)
class BillingSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "provider",
        "organization",
        "session_id",
        "plan_id",
        "billing_cycle",
        "status",
        "payment_status",
        "amount_usd",
        "updated_at",
    )
    list_filter = ("provider", "organization", "status", "billing_cycle", "payment_status")
    search_fields = (
        "session_id",
        "payment_intent_id",
        "plan_id",
        "plan_name",
        "reference",
        "registration_consumed_by_email",
        "organization__name",
        "organization__code",
    )
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


@admin.register(OrganizationOnboardingToken)
class OrganizationOnboardingTokenAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "organization",
        "subscription",
        "token_prefix",
        "is_active",
        "uses",
        "max_uses",
        "expires_at",
        "revoked_at",
        "updated_at",
    )
    list_filter = ("is_active", "organization", "allowed_email_domain")
    search_fields = (
        "organization__name",
        "organization__code",
        "subscription__reference",
        "token_prefix",
    )
    readonly_fields = ("token_hash", "created_at", "updated_at", "last_used_at", "revoked_at")
