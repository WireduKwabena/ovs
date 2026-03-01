from django.db import models


class BillingSubscription(models.Model):
    PROVIDER_CHOICES = (
        ("stripe", "Stripe"),
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

    def __str__(self) -> str:
        base = self.session_id or self.reference or str(self.pk)
        return f"{self.provider}:{base}:{self.status}"


class BillingWebhookEvent(models.Model):
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

