from django.db import migrations


class Migration(migrations.Migration):
    """
    Originally quarantined null-org records into a legacy sentinel org.
    Made a no-op: django-tenants schema isolation supersedes explicit org FKs,
    and the subsequent RemoveField migrations drop those columns entirely.
    """

    dependencies = [
        ("core", "0001_backfill_internal_org_from_linkage"),
        ("governance", "0002_committee_active_chair_constraint"),
    ]

    operations = [
        migrations.RunPython(migrations.RunPython.noop, migrations.RunPython.noop),
    ]
