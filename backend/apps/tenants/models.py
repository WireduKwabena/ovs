import uuid

from django.db import models
from django_tenants.models import DomainMixin, TenantMixin

class Organization(TenantMixin):
    ORGANIZATION_TYPE_CHOICES = [
        ("ministry", "Ministry"),
        ("agency", "Agency"),
        ("committee_secretariat", "Committee Secretariat"),
        ("executive_office", "Executive Office"),
        ("audit", "Audit Institution"),
        ("other", "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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

    auto_create_schema = True
    auto_drop_schema = True  
    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["is_active", "name"]),
        ]

    def __str__(self):
        return self.name




class Domain(DomainMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        app_label = 'tenants'