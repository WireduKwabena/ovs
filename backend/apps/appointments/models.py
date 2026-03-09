import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class ApprovalStageTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "governance.Organization",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approval_stage_templates",
    )
    name = models.CharField(max_length=200)
    exercise_type = models.CharField(max_length=50)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_approval_stage_templates",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["exercise_type", "name"]),
            models.Index(fields=["organization", "exercise_type"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.exercise_type})"


class ApprovalStage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(
        ApprovalStageTemplate,
        related_name="stages",
        on_delete=models.CASCADE,
    )
    order = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=100)
    required_role = models.CharField(max_length=50)
    is_required = models.BooleanField(default=True)
    maps_to_status = models.CharField(max_length=50)
    committee = models.ForeignKey(
        "governance.Committee",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approval_stages",
    )

    class Meta:
        ordering = ["template", "order"]
        constraints = [
            models.UniqueConstraint(fields=["template", "order"], name="uniq_approval_stage_template_order"),
        ]
        indexes = [
            models.Index(fields=["template", "committee"]),
        ]

    def __str__(self):
        return f"{self.template.name}: {self.order}. {self.name}"


class AppointmentRecord(models.Model):
    STATUS_CHOICES = [
        ("nominated", "Nominated"),
        ("under_vetting", "Under Vetting"),
        ("committee_review", "Committee Review"),
        ("confirmation_pending", "Awaiting Parliamentary Confirmation"),
        ("appointed", "Appointed"),
        ("rejected", "Rejected"),
        ("withdrawn", "Withdrawn"),
        ("serving", "Serving"),
        ("exited", "Exited"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "governance.Organization",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="appointment_records",
    )
    position = models.ForeignKey(
        "positions.GovernmentPosition",
        on_delete=models.PROTECT,
        related_name="appointment_records",
    )
    nominee = models.ForeignKey(
        "personnel.PersonnelRecord",
        on_delete=models.PROTECT,
        related_name="appointment_records",
    )
    appointment_exercise = models.ForeignKey(
        "campaigns.VettingCampaign",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="appointment_records",
    )
    nominated_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="nominations_submitted",
    )
    nominated_by_display = models.CharField(max_length=200)
    nominated_by_org = models.CharField(max_length=200, blank=True)
    nomination_date = models.DateField()
    vetting_case = models.ForeignKey(
        "applications.VettingCase",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="appointment_records",
    )
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="nominated", db_index=True)
    committee_recommendation = models.TextField(blank=True)
    committee = models.ForeignKey(
        "governance.Committee",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="appointment_records",
    )
    final_decision_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="appointment_decisions",
    )
    final_decision_by_display = models.CharField(max_length=200, blank=True)
    appointment_date = models.DateField(null=True, blank=True)
    gazette_number = models.CharField(max_length=100, blank=True)
    gazette_date = models.DateField(null=True, blank=True)
    exit_date = models.DateField(null=True, blank=True)
    exit_reason = models.TextField(blank=True)
    is_public = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["position"],
                condition=Q(status="serving"),
                name="uniq_appt_serving_per_position",
            ),
            models.UniqueConstraint(
                fields=["position", "nominee"],
                condition=Q(
                    status__in=[
                        "nominated",
                        "under_vetting",
                        "committee_review",
                        "confirmation_pending",
                        "appointed",
                        "serving",
                    ]
                ),
                name="uniq_appt_active_position_nominee",
            ),
            models.CheckConstraint(
                condition=Q(exit_date__isnull=True) | Q(status="exited"),
                name="chk_appt_exit_date_only_exited",
            ),
            models.CheckConstraint(
                condition=~Q(status="exited") | Q(exit_date__isnull=False),
                name="chk_appt_exited_requires_exit_date",
            ),
            models.CheckConstraint(
                condition=~Q(status__in=["serving", "exited"]) | Q(appointment_date__isnull=False),
                name="chk_appt_serving_exited_need_appointment_date",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "is_public"]),
            models.Index(fields=["position", "nominee"]),
            models.Index(fields=["nomination_date", "status"]),
            models.Index(fields=["position", "status", "created_at"], name="idx_appt_pos_status_created"),
            models.Index(fields=["organization", "status"], name="idx_appt_org_status"),
            models.Index(fields=["committee", "status"], name="idx_appt_committee_status"),
        ]

    def __str__(self):
        return f"{self.position.title} :: {self.nominee.full_name} ({self.status})"


class AppointmentPublication(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published"),
        ("revoked", "Revoked"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    appointment = models.OneToOneField(
        AppointmentRecord,
        on_delete=models.CASCADE,
        related_name="publication",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)
    publication_reference = models.CharField(max_length=150, blank=True)
    publication_document_hash = models.CharField(max_length=128, blank=True)
    publication_notes = models.TextField(blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="published_appointment_records",
    )
    published_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="revoked_appointment_records",
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    revocation_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(status="published") | Q(published_at__isnull=False),
                name="chk_apptpub_pub_has_ts",
            ),
            models.CheckConstraint(
                condition=~Q(status="revoked") | Q(revoked_at__isnull=False),
                name="chk_apptpub_rev_has_ts",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "published_at"], name="idx_apptpub_status_pubat"),
        ]

    def __str__(self):
        return f"{self.appointment_id} :: {self.status}"


class AppointmentStageAction(models.Model):
    ACTION_CHOICES = [
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("referred", "Referred Back"),
        ("deferred", "Deferred"),
        ("noted", "Noted / Progressed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    appointment = models.ForeignKey(
        AppointmentRecord,
        related_name="stage_actions",
        on_delete=models.CASCADE,
    )
    stage = models.ForeignKey(
        ApprovalStage,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )
    committee_membership = models.ForeignKey(
        "governance.CommitteeMembership",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="appointment_stage_actions",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
    )
    actor_role = models.CharField(max_length=50)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    reason_note = models.TextField(blank=True)
    evidence_links = models.JSONField(default=list, blank=True)
    previous_status = models.CharField(max_length=50)
    new_status = models.CharField(max_length=50)
    acted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["acted_at"]
        indexes = [
            models.Index(fields=["appointment", "acted_at"]),
            models.Index(fields=["committee_membership", "acted_at"]),
        ]

    def __str__(self):
        return f"{self.appointment_id} :: {self.previous_status} -> {self.new_status}"
