import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class BillingSubscription(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    organization = models.ForeignKey(
        "tenants.Organization",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="billing_subscriptions",
    )

    PROVIDER_CHOICES = (
        ("stripe", "Stripe"),
        ("paystack", "Paystack"),
        ("sandbox", "Sandbox"),
    )

    STATUS_CHOICES = (
        ("open", "Open"),
        ("complete", "Complete"),
        ("expired", "Expired"),
        ("canceled", "Canceled"),
        ("failed", "Failed"),
    )

    provider = models.CharField(max_length=32, choices=PROVIDER_CHOICES, default="stripe")
    session_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    payment_intent_id = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="open")
    payment_status = models.CharField(max_length=64, blank=True, default="")

    plan_id = models.CharField(max_length=64)
    plan_name = models.CharField(max_length=128)
    billing_cycle = models.CharField(max_length=16)
    payment_method = models.CharField(max_length=32, default="card")
    amount_usd = models.DecimalField(max_digits=10, decimal_places=2)

    checkout_url = models.URLField(blank=True, default="")
    reference = models.CharField(max_length=255, blank=True, default="")
    ticket_confirmed_at = models.DateTimeField(blank=True, null=True)
    ticket_expires_at = models.DateTimeField(blank=True, null=True)
    registration_consumed_at = models.DateTimeField(blank=True, null=True)
    registration_consumed_by_email = models.EmailField(blank=True, default='')

    metadata = models.JSONField(default=dict, blank=True)
    raw_last_payload = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = []

    def __str__(self) -> str:
        base = self.session_id or self.reference or str(self.pk)
        return f"{self.provider}:{base}:{self.status}"


class BillingWebhookEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    PROCESSING_STATUS_CHOICES = (
        ("received", "Received"),
        ("processed", "Processed"),
        ("ignored", "Ignored"),
        ("failed", "Failed"),
    )

    provider = models.CharField(max_length=32, default="stripe")
    event_id = models.CharField(max_length=255, blank=True, default="", db_index=True)
    event_type = models.CharField(max_length=255, blank=True, default="")
    signature = models.TextField(blank=True, default="")
    livemode = models.BooleanField(default=False)
    payload = models.JSONField(default=dict, blank=True)

    processing_status = models.CharField(
        max_length=16,
        choices=PROCESSING_STATUS_CHOICES,
        default="received",
    )
    processing_error = models.TextField(blank=True, default="")
    processed_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        identifier = self.event_id or str(self.pk)
        return f"{self.provider}:{identifier}:{self.processing_status}"


class OrganizationOnboardingToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(
        BillingSubscription,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="onboarding_tokens",
    )
    token_hash = models.CharField(max_length=128, unique=True, db_index=True)
    token_prefix = models.CharField(max_length=24, blank=True, default="", db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    max_uses = models.PositiveIntegerField(null=True, blank=True)
    uses = models.PositiveIntegerField(default=0)
    allowed_email_domain = models.CharField(max_length=255, blank=True, default="")
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.CharField(max_length=255, blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_organization_onboarding_tokens",
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(max_uses__isnull=True) | Q(max_uses__gt=0),
                name="chk_org_onboarding_token_max_uses_positive",
            ),
            models.CheckConstraint(
                condition=Q(uses__gte=0),
                name="chk_org_onboarding_token_uses_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(revoked_at__isnull=True) | Q(is_active=False),
                name="chk_org_onboarding_token_revoked_inactive",
            ),
        ]
        indexes = [
            models.Index(fields=["subscription", "is_active"], name="bill_onboard_sub_active_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.token_prefix}:{'active' if self.is_active else 'inactive'}"

