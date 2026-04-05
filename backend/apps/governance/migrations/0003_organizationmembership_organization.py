import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        # NOTE: "tenants.0001_initial" is intentionally omitted.  It is a
        # SHARED_APP migration that runs only in the public schema.  Including it
        # here would prevent this TENANT_APP migration from running in per-tenant
        # schemas (django-tenants doesn't propagate the public schema's migration
        # history to tenant schemas).  The FK constraint resolves correctly at
        # runtime because search_path includes the public schema.
        ("governance", "0002_committee_active_chair_constraint"),
    ]

    operations = [
        migrations.AddField(
            model_name="organizationmembership",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="memberships",
                to="tenants.organization",
            ),
        ),
    ]
