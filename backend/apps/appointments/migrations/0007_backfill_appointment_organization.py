from django.core.exceptions import FieldError
from django.db import migrations


def backfill_appointment_and_template_organization(apps, schema_editor):
    AppointmentRecord = apps.get_model("appointments", "AppointmentRecord")
    ApprovalStageTemplate = apps.get_model("appointments", "ApprovalStageTemplate")
    db_alias = schema_editor.connection.alias

    appointments = (
        AppointmentRecord.objects.using(db_alias)
        .filter(organization_id__isnull=True)
        .select_related(
            "appointment_exercise",
            "position",
            "nominee",
            "vetting_case",
        )
        .order_by("created_at")
    )

    appointment_rows = []
    for appointment in appointments.iterator(chunk_size=200):
        resolved_org_id = (
            getattr(appointment.appointment_exercise, "organization_id", None)
            or getattr(appointment.position, "organization_id", None)
            or getattr(appointment.nominee, "organization_id", None)
            or getattr(appointment.vetting_case, "organization_id", None)
        )
        if resolved_org_id:
            appointment.organization_id = resolved_org_id
            appointment_rows.append(appointment)

    if appointment_rows:
        AppointmentRecord.objects.using(db_alias).bulk_update(appointment_rows, ["organization"], batch_size=500)

    templates = (
        ApprovalStageTemplate.objects.using(db_alias)
        .filter(organization_id__isnull=True)
        .prefetch_related("campaigns")
        .order_by("created_at")
    )
    template_rows = []
    for template in templates.iterator(chunk_size=200):
        campaigns_fields = {field.name for field in template.campaigns.model._meta.get_fields()}
        if "organization" not in campaigns_fields:
            continue
        try:
            org_ids = {
                str(org_id)
                for org_id in template.campaigns.exclude(organization_id__isnull=True).values_list(
                    "organization_id",
                    flat=True,
                )
                if org_id
            }
        except FieldError:
            continue
        if len(org_ids) == 1:
            template.organization_id = next(iter(org_ids))
            template_rows.append(template)

    if template_rows:
        ApprovalStageTemplate.objects.using(db_alias).bulk_update(template_rows, ["organization"], batch_size=500)


class Migration(migrations.Migration):

    dependencies = [
        ("appointments", "0006_appointmentrecord_organization_and_more"),
        ("applications", "0004_backfill_vettingcase_organization"),
        ("campaigns", "0004_backfill_campaign_organization"),
        ("personnel", "0002_personnelrecord_organization_and_more"),
        ("positions", "0002_governmentposition_organization_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_appointment_and_template_organization, migrations.RunPython.noop),
    ]
