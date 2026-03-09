from __future__ import annotations

from django.db import transaction
from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import Organization, OrganizationMembership


def _membership_activation_consumes_seat(instance: OrganizationMembership) -> bool:
    if not bool(getattr(instance, "is_active", False)):
        return False

    if instance.pk is None:
        return True

    previous = (
        OrganizationMembership.objects.filter(pk=instance.pk)
        .values("organization_id", "is_active")
        .first()
    )
    if previous is None:
        return True

    previous_org_id = str(previous.get("organization_id") or "")
    current_org_id = str(getattr(instance, "organization_id", "") or "")
    if previous_org_id != current_org_id:
        return True

    return not bool(previous.get("is_active", False))


@receiver(pre_save, sender=OrganizationMembership)
def enforce_membership_seat_quota(sender, instance: OrganizationMembership, **kwargs):
    organization_id = str(getattr(instance, "organization_id", "") or "")
    if not organization_id:
        return

    if not _membership_activation_consumes_seat(instance):
        return

    from apps.billing.models import BillingSubscription
    from apps.billing.quotas import enforce_organization_seat_quota
    from apps.billing.services import get_active_subscription_for_organization

    with transaction.atomic():
        org_exists = (
            Organization.objects.select_for_update()
            .filter(id=organization_id, is_active=True)
            .exists()
        )
        if not org_exists:
            return

        active_subscription = get_active_subscription_for_organization(
            organization_id=organization_id
        )
        has_billing_history = BillingSubscription.objects.filter(
            organization_id=organization_id
        ).exists()

        # Backward-safe: do not block legacy organizations with no billing history.
        if active_subscription is None and not has_billing_history:
            return

        enforce_organization_seat_quota(
            organization_id=organization_id,
            subscription=active_subscription,
            additional=1,
        )
