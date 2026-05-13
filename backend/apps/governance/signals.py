from __future__ import annotations

from django.db import transaction
from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import OrganizationMembership


def _resolve_membership_organization_id(instance: OrganizationMembership) -> str:
    from apps.tenants.models import Organization

    user = getattr(instance, "user", None)
    legacy_org_name = str(getattr(user, "organization", "") or "").strip()
    if legacy_org_name:
        org = Organization.objects.filter(name__iexact=legacy_org_name, is_active=True).first()
        if org is not None:
            return str(org.id)

    default_org = (
        Organization.objects.filter(is_active=True)
        .exclude(schema_name="public")
        .order_by("name")
        .first()
    )
    if default_org is None:
        return ""
    return str(default_org.id)


def _membership_activation_consumes_seat(instance: OrganizationMembership) -> bool:
    if not bool(getattr(instance, "is_active", False)):
        return False

    if instance.pk is None:
        return True

    previous = (
        OrganizationMembership.objects.filter(pk=instance.pk)
        .values("is_active")
        .first()
    )
    if previous is None:
        return True

    return not bool(previous.get("is_active", False))


@receiver(pre_save, sender=OrganizationMembership)
def enforce_membership_seat_quota(sender, instance: OrganizationMembership, **kwargs):
    organization_id = _resolve_membership_organization_id(instance)

    if not organization_id:
        return

    if not _membership_activation_consumes_seat(instance):
        return

    from apps.core.quotas import enforce_membership_activation_seat_quota

    with transaction.atomic():
        enforce_membership_activation_seat_quota(
            organization_id=organization_id,
            additional=1,
        )
