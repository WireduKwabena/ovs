from django.db import migrations


class Migration(migrations.Migration):
    """
    Originally backfilled organization FKs on tenant-app models.
    Made a no-op: django-tenants schema isolation supersedes explicit org FKs,
    and the subsequent RemoveField migrations drop those columns entirely.
    """
    initial = True

    dependencies = [
        ("applications", "0004_backfill_vettingcase_organization"),
        ("appointments", "0008_appointmentrecord_committee_and_more"),
        ("campaigns", "0004_backfill_campaign_organization"),
        ("governance", "0002_committee_active_chair_constraint"),
        ("personnel", "0002_personnelrecord_organization_and_more"),
        ("positions", "0002_governmentposition_organization_and_more"),
        ("rubrics", "0003_vettingrubric_organization_and_more"),
    ]

    operations = [
        migrations.RunPython(migrations.RunPython.noop, migrations.RunPython.noop),
    ]
