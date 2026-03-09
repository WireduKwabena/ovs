from django.db import migrations


def backfill_campaign_organization(apps, schema_editor):
    VettingCampaign = apps.get_model("campaigns", "VettingCampaign")
    OrganizationMembership = apps.get_model("governance", "OrganizationMembership")
    db_alias = schema_editor.connection.alias

    campaigns = (
        VettingCampaign.objects.using(db_alias)
        .filter(organization_id__isnull=True)
        .select_related("approval_template", "initiated_by")
        .prefetch_related("positions")
        .order_by("created_at")
    )

    rows_to_update = []
    for campaign in campaigns.iterator(chunk_size=200):
        resolved_org_id = None

        if getattr(campaign, "approval_template_id", None):
            resolved_org_id = getattr(campaign.approval_template, "organization_id", None)

        if resolved_org_id is None:
            # Keep this migration resilient for environments where historical position
            # schema may not yet include ``organization`` during graph resolution.
            position_fields = {field.name for field in campaign.positions.model._meta.get_fields()}
            if "organization" in position_fields:
                position_org_ids = {
                    str(org_id)
                    for org_id in campaign.positions.exclude(organization_id__isnull=True).values_list(
                        "organization_id", flat=True
                    )
                    if org_id
                }
                has_unscoped_positions = campaign.positions.filter(organization_id__isnull=True).exists()
                if len(position_org_ids) == 1 and not has_unscoped_positions:
                    resolved_org_id = next(iter(position_org_ids))

        if resolved_org_id is None and getattr(campaign, "initiated_by_id", None):
            memberships = (
                OrganizationMembership.objects.using(db_alias)
                .filter(user_id=campaign.initiated_by_id, is_active=True)
                .order_by("-is_default", "created_at")
            )
            default_membership = memberships.filter(is_default=True).first()
            if default_membership is not None:
                resolved_org_id = default_membership.organization_id
            elif memberships.count() == 1:
                resolved_org_id = memberships.first().organization_id

        if resolved_org_id:
            campaign.organization_id = resolved_org_id
            rows_to_update.append(campaign)

    if rows_to_update:
        VettingCampaign.objects.using(db_alias).bulk_update(rows_to_update, ["organization"], batch_size=500)


class Migration(migrations.Migration):

    dependencies = [
        ("campaigns", "0003_vettingcampaign_organization_and_more"),
        ("governance", "0001_initial"),
        ("positions", "0002_governmentposition_organization_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_campaign_organization, migrations.RunPython.noop),
    ]
