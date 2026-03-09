from django.db import migrations


LEGACY_QUARANTINE_CODE = "legacy-unscoped"
LEGACY_QUARANTINE_NAME = "Legacy Unscoped Records"


def quarantine_null_internal_org_records(apps, schema_editor):
    Organization = apps.get_model("governance", "Organization")
    GovernmentPosition = apps.get_model("positions", "GovernmentPosition")
    PersonnelRecord = apps.get_model("personnel", "PersonnelRecord")
    VettingCampaign = apps.get_model("campaigns", "VettingCampaign")
    VettingCase = apps.get_model("applications", "VettingCase")
    ApprovalStageTemplate = apps.get_model("appointments", "ApprovalStageTemplate")
    AppointmentRecord = apps.get_model("appointments", "AppointmentRecord")
    VettingRubric = apps.get_model("rubrics", "VettingRubric")
    db_alias = schema_editor.connection.alias

    quarantine_org, _created = Organization.objects.using(db_alias).get_or_create(
        code=LEGACY_QUARANTINE_CODE,
        defaults={
            "name": LEGACY_QUARANTINE_NAME,
            "organization_type": "other",
            "is_active": True,
            "metadata": {
                "system_managed": True,
                "purpose": "tenant_quarantine_for_legacy_null_org_records",
            },
        },
    )

    if quarantine_org.name != LEGACY_QUARANTINE_NAME or not quarantine_org.is_active:
        quarantine_org.name = LEGACY_QUARANTINE_NAME
        quarantine_org.is_active = True
        metadata = quarantine_org.metadata if isinstance(quarantine_org.metadata, dict) else {}
        metadata.setdefault("system_managed", True)
        metadata.setdefault("purpose", "tenant_quarantine_for_legacy_null_org_records")
        quarantine_org.metadata = metadata
        quarantine_org.save(update_fields=["name", "is_active", "metadata", "updated_at"])

    target_models = (
        GovernmentPosition,
        PersonnelRecord,
        VettingCampaign,
        VettingCase,
        ApprovalStageTemplate,
        AppointmentRecord,
        VettingRubric,
    )
    for model in target_models:
        model.objects.using(db_alias).filter(organization_id__isnull=True).update(
            organization_id=quarantine_org.id
        )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_backfill_internal_org_from_linkage"),
        ("governance", "0002_committee_active_chair_constraint"),
    ]

    operations = [
        migrations.RunPython(quarantine_null_internal_org_records, migrations.RunPython.noop),
    ]

