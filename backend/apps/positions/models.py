import uuid

from django.db import models


class GovernmentPosition(models.Model):
    BRANCH_CHOICES = [
        ("executive", "Executive"),
        ("legislative", "Legislative"),
        ("judicial", "Judicial"),
        ("independent", "Independent Body"),
        ("local", "Local Government"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    branch = models.CharField(max_length=20, choices=BRANCH_CHOICES, db_index=True)
    institution = models.CharField(max_length=200)
    appointment_authority = models.CharField(max_length=200)
    confirmation_required = models.BooleanField(default=False)
    constitutional_basis = models.TextField(blank=True)
    term_length_years = models.PositiveSmallIntegerField(null=True, blank=True)
    required_qualifications = models.TextField(blank=True)
    is_vacant = models.BooleanField(default=True, db_index=True)
    is_public = models.BooleanField(default=True, db_index=True)
    current_holder = models.ForeignKey(
        "personnel.PersonnelRecord",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="current_positions",
    )
    rubric = models.ForeignKey(
        "rubrics.VettingRubric",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="government_positions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]
        indexes = [
            models.Index(fields=["branch", "institution"]),
            models.Index(fields=["is_public", "is_vacant"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.institution})"
