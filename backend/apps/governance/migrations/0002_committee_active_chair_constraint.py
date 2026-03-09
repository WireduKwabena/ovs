from django.db import migrations, models
from django.db.models import Count, Q
from django.utils import timezone


def normalize_active_committee_chairs(apps, schema_editor):
    CommitteeMembership = apps.get_model("governance", "CommitteeMembership")
    db_alias = schema_editor.connection.alias

    duplicate_committee_ids = list(
        CommitteeMembership.objects.using(db_alias)
        .filter(committee_role="chair", is_active=True)
        .values("committee_id")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
        .values_list("committee_id", flat=True)
    )

    if not duplicate_committee_ids:
        return

    now = timezone.now()
    for committee_id in duplicate_committee_ids:
        chairs = list(
            CommitteeMembership.objects.using(db_alias)
            .filter(
                committee_id=committee_id,
                committee_role="chair",
                is_active=True,
            )
            .order_by("joined_at", "created_at", "id")
        )

        if len(chairs) < 2:
            continue

        demoted_rows = chairs[1:]
        for row in demoted_rows:
            row.committee_role = "member"
            row.updated_at = now

        CommitteeMembership.objects.using(db_alias).bulk_update(
            demoted_rows,
            ["committee_role", "updated_at"],
            batch_size=500,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("governance", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            normalize_active_committee_chairs,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="committeemembership",
            constraint=models.UniqueConstraint(
                condition=Q(committee_role="chair", is_active=True),
                fields=("committee",),
                name="uniq_active_committee_chair_per_committee",
            ),
        ),
    ]
