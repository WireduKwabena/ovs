import uuid

from django.db import models

class Organization(models.Model):
    ORGANIZATION_TYPE_CHOICES = [
        ("ministry", "Ministry"),
        ("agency", "Agency"),
        ("committee_secretariat", "Committee Secretariat"),
        ("executive_office", "Executive Office"),
        ("other", "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    schema_name = models.CharField(max_length=63, unique=True, db_index=True)
    code = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=200, unique=True)
    organization_type = models.CharField(max_length=30, choices=ORGANIZATION_TYPE_CHOICES, default="other")
    is_active = models.BooleanField(default=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Subscription / tier
    tier = models.CharField(
        max_length=20,
        choices=[
            ('trial', 'Trial'),
            ('starter', 'Starter'),
            ('growth', 'Growth'),
            ('enterprise', 'Enterprise'),
        ],
        default='starter',
    )
    subscription_expires_at = models.DateTimeField(null=True, blank=True)

    auto_create_schema = False
    auto_drop_schema = False

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["is_active", "name"], name="tenants_org_is_acti_c2ed40_idx"),
        ]

    @staticmethod
    def _derive_schema_name(code: str) -> str:
        normalized = (code or "org").replace("-", "_").lower()[:50]
        return f"org_{normalized}"

    def save(self, *args, **kwargs):
        if not self.schema_name:
            self.schema_name = self._derive_schema_name(self.code)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name




class Domain(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.CharField(max_length=253, unique=True, db_index=True)
    is_primary = models.BooleanField(default=True, db_index=True)
    tenant = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="domains",
        db_index=True,
    )

    class Meta:
        app_label = 'tenants'