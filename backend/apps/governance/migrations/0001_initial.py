import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="OrganizationMembership",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(blank=True, max_length=120)),
                ("membership_role", models.CharField(blank=True, max_length=80)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("is_default", models.BooleanField(db_index=True, default=False)),
                ("joined_at", models.DateTimeField(blank=True, null=True)),
                ("left_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="organization_memberships",
                        to=settings.AUTH_USER_MODEL,
                        db_constraint=False,
                    ),
                ),
            ],
            options={
                "ordering": ["-is_default", "created_at"],
                "indexes": [
                    models.Index(fields=["user", "is_active"], name="governance__user_id_5d7fa7_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(is_active=True, is_default=True),
                        fields=("user",),
                        name="uniq_org_membership_active_default_per_user",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(left_at__isnull=True) | models.Q(is_active=False),
                        name="chk_org_membership_left_at_requires_inactive",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(is_default=False) | models.Q(is_active=True),
                        name="chk_org_membership_default_requires_active",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="Committee",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.SlugField(max_length=80, unique=True)),
                ("name", models.CharField(max_length=200, unique=True)),
                (
                    "committee_type",
                    models.CharField(
                        choices=[
                            ("screening", "Screening"),
                            ("vetting", "Vetting"),
                            ("approval", "Approval"),
                            ("publication", "Publication"),
                            ("oversight", "Oversight"),
                            ("other", "Other"),
                        ],
                        default="other",
                        max_length=30,
                    ),
                ),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_committees",
                        to=settings.AUTH_USER_MODEL,
                        db_constraint=False,
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
                "indexes": [
                    models.Index(fields=["committee_type", "is_active"], name="governance__committ_b00c7f_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="CommitteeMembership",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "committee_role",
                    models.CharField(
                        choices=[
                            ("chair", "Chair"),
                            ("member", "Member"),
                            ("secretary", "Secretary"),
                            ("observer", "Observer"),
                        ],
                        default="member",
                        max_length=20,
                    ),
                ),
                ("can_vote", models.BooleanField(default=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("joined_at", models.DateTimeField(blank=True, null=True)),
                ("left_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "committee",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memberships",
                        to="governance.committee",
                    ),
                ),
                (
                    "organization_membership",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="committee_memberships",
                        to="governance.organizationmembership",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="committee_memberships",
                        to=settings.AUTH_USER_MODEL,
                        db_constraint=False,
                    ),
                ),
            ],
            options={
                "ordering": ["committee__name", "committee_role", "created_at"],
                "indexes": [
                    models.Index(fields=["committee", "is_active"], name="governance__committ_4b5df2_idx"),
                    models.Index(fields=["user", "is_active"], name="governance__user_id_cc25cf_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("committee", "user"),
                        name="uniq_committee_membership_committee_user",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(left_at__isnull=True) | models.Q(is_active=False),
                        name="chk_committee_membership_left_at_requires_inactive",
                    ),
                    models.CheckConstraint(
                        condition=~models.Q(committee_role="observer") | models.Q(can_vote=False),
                        name="chk_committee_observer_non_voting",
                    ),
                ],
            },
        ),
    ]
