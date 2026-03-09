from django.db import migrations


def backfill_vettingcase_organization(apps, schema_editor):
    VettingCase = apps.get_model("applications", "VettingCase")
    db_alias = schema_editor.connection.alias

    cases = (
        VettingCase.objects.using(db_alias)
        .filter(organization_id__isnull=True, candidate_enrollment_id__isnull=False)
        .select_related("candidate_enrollment", "candidate_enrollment__campaign")
        .order_by("created_at")
    )

    rows_to_update = []
    for case in cases.iterator():
        enrollment = getattr(case, "candidate_enrollment", None)
        campaign = getattr(enrollment, "campaign", None)
        resolved_org_id = getattr(campaign, "organization_id", None)
        if resolved_org_id:
            case.organization_id = resolved_org_id
            rows_to_update.append(case)

    if rows_to_update:
        VettingCase.objects.using(db_alias).bulk_update(rows_to_update, ["organization"], batch_size=500)


class Migration(migrations.Migration):

    dependencies = [
        ("applications", "0003_vettingcase_organization_and_more"),
        ("campaigns", "0004_backfill_campaign_organization"),
    ]

    operations = [
        migrations.RunPython(backfill_vettingcase_organization, migrations.RunPython.noop),
    ]
