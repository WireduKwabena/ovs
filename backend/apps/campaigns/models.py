import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class VettingCampaign(models.Model):
    EXERCISE_TYPE_CHOICES = [
        ("ministerial", "Ministerial"),
        ("judicial", "Judicial"),
        ("board", "Board / Commission"),
        ("local_gov", "Local Government"),
        ("diplomatic", "Diplomatic"),
        ("security", "Security Services"),
    ]

    BRANCH_CHOICES = [
        ("executive", "Executive"),
        ("legislative", "Legislative"),
        ("judicial", "Judicial"),
        ("independent", "Independent Body"),
        ("local", "Local Government"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("closed", "Closed"),
        ("archived", "Archived"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "governance.Organization",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="vetting_campaigns",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    settings_json = models.JSONField(default=dict, blank=True)
    exercise_type = models.CharField(max_length=30, choices=EXERCISE_TYPE_CHOICES, blank=True, db_index=True)
    jurisdiction = models.CharField(max_length=20, choices=BRANCH_CHOICES, blank=True, db_index=True)
    positions = models.ManyToManyField(
        "positions.GovernmentPosition",
        blank=True,
        related_name="appointment_exercises",
    )
    approval_template = models.ForeignKey(
        "appointments.ApprovalStageTemplate",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="campaigns",
    )
    appointment_authority = models.CharField(max_length=200, blank=True)
    requires_parliamentary_confirmation = models.BooleanField(default=False)
    gazette_reference = models.CharField(max_length=100, blank=True)

    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="initiated_campaigns",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["initiated_by", "status"]),
            models.Index(fields=["exercise_type", "jurisdiction"]),
            models.Index(fields=["organization", "status"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.status})"


class CampaignRubricVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    campaign = models.ForeignKey(
        VettingCampaign,
        on_delete=models.CASCADE,
        related_name="rubric_versions",
    )
    version = models.PositiveIntegerField()
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    weight_document = models.PositiveSmallIntegerField(
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    weight_interview = models.PositiveSmallIntegerField(
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    passing_score = models.PositiveSmallIntegerField(
        default=70,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    auto_approve_threshold = models.PositiveSmallIntegerField(
        default=90,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    auto_reject_threshold = models.PositiveSmallIntegerField(
        default=40,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    rubric_payload = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=False, db_index=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_campaign_rubric_versions",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["campaign", "version"], name="uniq_campaign_rubric_version"),
        ]

    def clean(self):
        if (self.weight_document + self.weight_interview) != 100:
            raise ValidationError("Rubric weights must add up to 100.")

        if self.auto_approve_threshold <= self.passing_score:
            raise ValidationError("Auto-approve threshold must be greater than passing score.")

        if self.auto_reject_threshold >= self.passing_score:
            raise ValidationError("Auto-reject threshold must be lower than passing score.")

    def save(self, *args, **kwargs):
        self.full_clean()

        if self.is_active:
            CampaignRubricVersion.objects.filter(campaign=self.campaign, is_active=True).exclude(pk=self.pk).update(
                is_active=False
            )

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.campaign.name} - v{self.version}"
