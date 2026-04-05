import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone


class OrganizationMembership(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_memberships",
    )
    organization = models.ForeignKey(
        "tenants.Organization",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    title = models.CharField(max_length=120, blank=True)
    membership_role = models.CharField(max_length=80, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    is_default = models.BooleanField(default=False, db_index=True)
    joined_at = models.DateTimeField(null=True, blank=True)
    left_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(is_default=True, is_active=True),
                name="uniq_org_membership_active_default_per_user",
            ),
            models.CheckConstraint(
                condition=Q(left_at__isnull=True) | Q(is_active=False),
                name="chk_org_membership_left_at_requires_inactive",
            ),
            models.CheckConstraint(
                condition=Q(is_default=False) | Q(is_active=True),
                name="chk_org_membership_default_requires_active",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self):
        return f"{self.user_id} (membership)"


class Committee(models.Model):
    COMMITTEE_TYPE_CHOICES = [
        ("screening", "Screening"),
        ("vetting", "Vetting"),
        ("approval", "Approval"),
        ("publication", "Publication"),
        ("oversight", "Oversight"),
        ("other", "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=200, unique=True)
    committee_type = models.CharField(max_length=30, choices=COMMITTEE_TYPE_CHOICES, default="other")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_committees",
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["committee_type", "is_active"]),
        ]

    def __str__(self):
        return self.name


class CommitteeMembership(models.Model):
    COMMITTEE_ROLE_CHOICES = [
        ("chair", "Chair"),
        ("member", "Member"),
        ("secretary", "Secretary"),
        ("observer", "Observer"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    committee = models.ForeignKey(
        Committee,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="committee_memberships",
    )
    organization_membership = models.ForeignKey(
        OrganizationMembership,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="committee_memberships",
    )
    committee_role = models.CharField(max_length=20, choices=COMMITTEE_ROLE_CHOICES, default="member")
    can_vote = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True, db_index=True)
    joined_at = models.DateTimeField(null=True, blank=True)
    left_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["committee__name", "committee_role", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["committee", "user"],
                name="uniq_committee_membership_committee_user",
            ),
            models.UniqueConstraint(
                fields=["committee"],
                condition=Q(committee_role="chair", is_active=True),
                name="uniq_active_committee_chair_per_committee",
            ),
            models.CheckConstraint(
                condition=Q(left_at__isnull=True) | Q(is_active=False),
                name="chk_committee_membership_left_at_requires_inactive",
            ),
            models.CheckConstraint(
                condition=~Q(committee_role="observer") | Q(can_vote=False),
                name="chk_committee_observer_non_voting",
            ),
        ]
        indexes = [
            models.Index(fields=["committee", "is_active"]),
            models.Index(fields=["user", "is_active"]),
        ]

    @classmethod
    def assign_active_chair(
        cls,
        *,
        committee,
        user,
        organization_membership=None,
        can_vote=True,
    ):
        if committee is None:
            raise ValidationError("Committee is required.")
        if user is None:
            raise ValidationError("User is required.")

        with transaction.atomic():
            committee_locked = Committee.objects.select_for_update().get(pk=committee.pk)

            if organization_membership is not None:
                if getattr(organization_membership, "user_id", None) != getattr(user, "id", None):
                    raise ValidationError(
                        "Organization membership user must match committee membership user."
                    )
                if not bool(getattr(organization_membership, "is_active", False)):
                    raise ValidationError("Organization membership must be active.")
            else:
                organization_membership = (
                    OrganizationMembership.objects.select_for_update()
                    .filter(
                        user=user,
                        is_active=True,
                    )
                    .order_by("-is_default", "created_at")
                    .first()
                )

            # Demote any other active chair memberships first, then promote target.
            cls.objects.select_for_update().filter(
                committee=committee_locked,
                committee_role="chair",
                is_active=True,
            ).exclude(
                user=user
            ).update(
                committee_role="member",
                updated_at=timezone.now(),
            )

            membership, _created = cls.objects.select_for_update().get_or_create(
                committee=committee_locked,
                user=user,
                defaults={
                    "organization_membership": organization_membership,
                    "committee_role": "chair",
                    "can_vote": bool(can_vote),
                    "is_active": True,
                    "joined_at": timezone.now(),
                    "left_at": None,
                },
            )

            changed_fields: list[str] = []
            if membership.organization_membership_id != getattr(organization_membership, "id", None):
                membership.organization_membership = organization_membership
                changed_fields.append("organization_membership")
            if membership.committee_role != "chair":
                membership.committee_role = "chair"
                changed_fields.append("committee_role")
            if membership.can_vote != bool(can_vote):
                membership.can_vote = bool(can_vote)
                changed_fields.append("can_vote")
            if not membership.is_active:
                membership.is_active = True
                changed_fields.append("is_active")
            if membership.left_at is not None:
                membership.left_at = None
                changed_fields.append("left_at")
            if membership.joined_at is None:
                membership.joined_at = timezone.now()
                changed_fields.append("joined_at")

            if changed_fields:
                membership.save(update_fields=changed_fields + ["updated_at"])

            return membership

    def __str__(self):
        return f"{self.user_id} :: {self.committee.name} ({self.committee_role})"
