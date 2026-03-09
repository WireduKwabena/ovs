from django.db import migrations


def _single_org_id(values) -> str | None:
    unique = []
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in unique:
            continue
        unique.append(normalized)
    if len(unique) == 1:
        return unique[0]
    return None


def backfill_internal_org_from_linkage(apps, schema_editor):
    GovernmentPosition = apps.get_model("positions", "GovernmentPosition")
    PersonnelRecord = apps.get_model("personnel", "PersonnelRecord")
    VettingCampaign = apps.get_model("campaigns", "VettingCampaign")
    VettingCase = apps.get_model("applications", "VettingCase")
    ApprovalStageTemplate = apps.get_model("appointments", "ApprovalStageTemplate")
    AppointmentRecord = apps.get_model("appointments", "AppointmentRecord")
    VettingRubric = apps.get_model("rubrics", "VettingRubric")
    OrganizationMembership = apps.get_model("governance", "OrganizationMembership")
    db_alias = schema_editor.connection.alias

    position_rows = []
    for row in (
        GovernmentPosition.objects.using(db_alias)
        .filter(organization_id__isnull=True)
        .select_related("current_holder")
        .prefetch_related("appointment_records")
        .iterator(chunk_size=200)
    ):
        candidate_orgs = []
        if getattr(row, "current_holder_id", None):
            candidate_orgs.append(getattr(row.current_holder, "organization_id", None))
        candidate_orgs.extend(
            row.appointment_records.exclude(organization_id__isnull=True).values_list("organization_id", flat=True)
        )
        resolved = _single_org_id(candidate_orgs)
        if resolved:
            row.organization_id = resolved
            position_rows.append(row)
    if position_rows:
        GovernmentPosition.objects.using(db_alias).bulk_update(position_rows, ["organization"], batch_size=500)

    personnel_rows = []
    for row in (
        PersonnelRecord.objects.using(db_alias)
        .filter(organization_id__isnull=True)
        .prefetch_related("current_positions", "appointment_records")
        .iterator(chunk_size=200)
    ):
        candidate_orgs = []
        candidate_orgs.extend(row.current_positions.exclude(organization_id__isnull=True).values_list("organization_id", flat=True))
        candidate_orgs.extend(
            row.appointment_records.exclude(organization_id__isnull=True).values_list("organization_id", flat=True)
        )
        resolved = _single_org_id(candidate_orgs)
        if resolved:
            row.organization_id = resolved
            personnel_rows.append(row)
    if personnel_rows:
        PersonnelRecord.objects.using(db_alias).bulk_update(personnel_rows, ["organization"], batch_size=500)

    campaign_rows = []
    for row in (
        VettingCampaign.objects.using(db_alias)
        .filter(organization_id__isnull=True)
        .select_related("approval_template")
        .prefetch_related("positions")
        .iterator(chunk_size=200)
    ):
        candidate_orgs = []
        candidate_orgs.append(getattr(getattr(row, "approval_template", None), "organization_id", None))
        candidate_orgs.extend(row.positions.exclude(organization_id__isnull=True).values_list("organization_id", flat=True))

        if getattr(row, "initiated_by_id", None):
            memberships = (
                OrganizationMembership.objects.using(db_alias)
                .filter(user_id=row.initiated_by_id, is_active=True)
                .order_by("-is_default", "created_at")
            )
            default_membership = memberships.filter(is_default=True).first()
            if default_membership is not None:
                candidate_orgs.append(default_membership.organization_id)
            else:
                membership_org_id = _single_org_id(memberships.values_list("organization_id", flat=True))
                if membership_org_id:
                    candidate_orgs.append(membership_org_id)

        resolved = _single_org_id(candidate_orgs)
        if resolved:
            row.organization_id = resolved
            campaign_rows.append(row)
    if campaign_rows:
        VettingCampaign.objects.using(db_alias).bulk_update(campaign_rows, ["organization"], batch_size=500)

    case_rows = []
    for row in (
        VettingCase.objects.using(db_alias)
        .filter(organization_id__isnull=True)
        .select_related("candidate_enrollment", "candidate_enrollment__campaign")
        .prefetch_related("appointment_records")
        .iterator(chunk_size=200)
    ):
        candidate_orgs = []
        enrollment = getattr(row, "candidate_enrollment", None)
        campaign = getattr(enrollment, "campaign", None)
        candidate_orgs.append(getattr(campaign, "organization_id", None))
        candidate_orgs.extend(
            row.appointment_records.exclude(organization_id__isnull=True).values_list("organization_id", flat=True)
        )
        resolved = _single_org_id(candidate_orgs)
        if resolved:
            row.organization_id = resolved
            case_rows.append(row)
    if case_rows:
        VettingCase.objects.using(db_alias).bulk_update(case_rows, ["organization"], batch_size=500)

    template_rows = []
    for row in (
        ApprovalStageTemplate.objects.using(db_alias)
        .filter(organization_id__isnull=True)
        .prefetch_related("campaigns")
        .iterator(chunk_size=200)
    ):
        resolved = _single_org_id(row.campaigns.exclude(organization_id__isnull=True).values_list("organization_id", flat=True))
        if resolved:
            row.organization_id = resolved
            template_rows.append(row)
    if template_rows:
        ApprovalStageTemplate.objects.using(db_alias).bulk_update(template_rows, ["organization"], batch_size=500)

    appointment_rows = []
    for row in (
        AppointmentRecord.objects.using(db_alias)
        .filter(organization_id__isnull=True)
        .select_related("position", "nominee", "appointment_exercise", "vetting_case")
        .iterator(chunk_size=200)
    ):
        resolved = _single_org_id(
            [
                getattr(getattr(row, "position", None), "organization_id", None),
                getattr(getattr(row, "nominee", None), "organization_id", None),
                getattr(getattr(row, "appointment_exercise", None), "organization_id", None),
                getattr(getattr(row, "vetting_case", None), "organization_id", None),
            ]
        )
        if resolved:
            row.organization_id = resolved
            appointment_rows.append(row)
    if appointment_rows:
        AppointmentRecord.objects.using(db_alias).bulk_update(appointment_rows, ["organization"], batch_size=500)

    rubric_rows = []
    for row in (
        VettingRubric.objects.using(db_alias)
        .filter(organization_id__isnull=True)
        .prefetch_related("government_positions")
        .iterator(chunk_size=200)
    ):
        resolved = _single_org_id(
            row.government_positions.exclude(organization_id__isnull=True).values_list("organization_id", flat=True)
        )
        if resolved:
            row.organization_id = resolved
            rubric_rows.append(row)
    if rubric_rows:
        VettingRubric.objects.using(db_alias).bulk_update(rubric_rows, ["organization"], batch_size=500)


class Migration(migrations.Migration):
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
        migrations.RunPython(backfill_internal_org_from_linkage, migrations.RunPython.noop),
    ]

