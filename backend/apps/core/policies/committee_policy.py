"""Committee authorization policy helpers."""

from __future__ import annotations


def _is_authenticated(user) -> bool:
    return bool(getattr(user, "is_authenticated", False))


def get_active_committee_membership(
    *,
    user,
    committee,
    allow_observer: bool = False,
):
    if not _is_authenticated(user):
        return None
    committee_id = getattr(committee, "id", None)
    if committee_id is None:
        return None

    try:
        from apps.governance.models import CommitteeMembership
    except Exception:  # pragma: no cover - governance app may be unavailable in partial installs
        return None

    queryset = CommitteeMembership.objects.select_related("committee").filter(
        user=user,
        committee_id=committee_id,
        is_active=True,
        committee__is_active=True,
    )
    if not allow_observer:
        queryset = queryset.exclude(committee_role="observer")
    return queryset.order_by("-created_at").first()


def has_active_committee_membership(
    *,
    user,
    committee,
    allow_observer: bool = False,
) -> bool:
    membership = get_active_committee_membership(
        user=user,
        committee=committee,
        allow_observer=allow_observer,
    )
    return membership is not None


def has_active_membership_for_any_committee_ids(
    *,
    user,
    committee_ids,
    allow_observer: bool = False,
) -> bool:
    if not _is_authenticated(user):
        return False

    normalized_committee_ids = [value for value in committee_ids if value]
    if not normalized_committee_ids:
        return False

    try:
        from apps.governance.models import CommitteeMembership
    except Exception:  # pragma: no cover - governance app may be unavailable in partial installs
        return False

    queryset = CommitteeMembership.objects.filter(
        user=user,
        committee_id__in=normalized_committee_ids,
        is_active=True,
        committee__is_active=True,
    )
    if not allow_observer:
        queryset = queryset.exclude(committee_role="observer")
    return queryset.exists()

