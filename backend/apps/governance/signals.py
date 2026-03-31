from __future__ import annotations

from django.db import connection, transaction
from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import OrganizationMembership


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
    # In the django-tenants setup, the organization is the current tenant schema.
    try:
        organization_id = str(connection.tenant.id)
    except Exception:
        return

    if not organization_id:
        return

    if not _membership_activation_consumes_seat(instance):
        return

    from apps.billing.quotas import enforce_membership_activation_seat_quota

    with transaction.atomic():
        enforce_membership_activation_seat_quota(
            organization_id=organization_id,
            additional=1,
        )
