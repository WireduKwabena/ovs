import uuid

from django.db import models


class PersonnelRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=200)
    date_of_birth = models.DateField(null=True, blank=True)
    nationality = models.CharField(max_length=100, default="Ghanaian")
    national_id_hash = models.CharField(max_length=128, blank=True)
    national_id_encrypted = models.CharField(max_length=255, blank=True)
    gender = models.CharField(max_length=20, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=30, blank=True)
    bio_summary = models.TextField(blank=True)
    academic_qualifications = models.JSONField(default=list, blank=True)
    professional_history = models.JSONField(default=list, blank=True)
    is_active_officeholder = models.BooleanField(default=False, db_index=True)
    is_public = models.BooleanField(default=True, db_index=True)
    linked_candidate = models.OneToOneField(
        "candidates.Candidate",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="personnel_record",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name"]
        indexes = [
            models.Index(fields=["is_active_officeholder", "is_public"]),
        ]

    def __str__(self):
        return self.full_name
