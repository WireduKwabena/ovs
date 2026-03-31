import uuid

import django.db.models.deletion
import django_tenants.postgresql_backend.base
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Organization",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "schema_name",
                    models.CharField(
                        db_index=True,
                        max_length=63,
                        unique=True,
                        validators=[django_tenants.postgresql_backend.base._check_schema_name],
                    ),
                ),
                ("code", models.SlugField(max_length=80, unique=True)),
                ("name", models.CharField(max_length=200, unique=True)),
                (
                    "organization_type",
                    models.CharField(
                        choices=[
                            ("ministry", "Ministry"),
                            ("agency", "Agency"),
                            ("committee_secretariat", "Committee Secretariat"),
                            ("executive_office", "Executive Office"),
                            ("audit", "Audit Institution"),
                            ("other", "Other"),
                        ],
                        default="other",
                        max_length=30,
                    ),
                ),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                (
                    "tier",
                    models.CharField(
                        choices=[
                            ("pilot", "Pilot — free"),
                            ("standard", "Standard"),
                            ("premium", "Premium — dedicated infra"),
                        ],
                        default="pilot",
                        max_length=20,
                    ),
                ),
                ("subscription_expires_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["name"],
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="Domain",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "domain",
                    models.CharField(db_index=True, max_length=253, unique=True),
                ),
                (
                    "is_primary",
                    models.BooleanField(db_index=True, default=True),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="domains",
                        to="tenants.organization",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
    ]
