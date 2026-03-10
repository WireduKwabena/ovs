"""Read-only public transparency query helpers."""

from __future__ import annotations

from django.db.models import Q

from apps.personnel.models import PersonnelRecord
from apps.positions.models import GovernmentPosition

from .models import AppointmentRecord

OPEN_PUBLIC_APPOINTMENT_STATUSES = {
    "nominated",
    "under_vetting",
    "committee_review",
    "confirmation_pending",
}

PUBLIC_APPOINTMENT_ORDERING_FIELDS = {
    "published_at": "publication__published_at",
    "-published_at": "-publication__published_at",
    "appointment_date": "appointment_date",
    "-appointment_date": "-appointment_date",
    "gazette_date": "gazette_date",
    "-gazette_date": "-gazette_date",
    "nomination_date": "nomination_date",
    "-nomination_date": "-nomination_date",
    "status": "status",
    "-status": "-status",
}


def published_appointments_queryset(*, require_gazette_number: bool = False):
    queryset = AppointmentRecord.objects.select_related(
        "position",
        "nominee",
        "publication",
    ).filter(
        is_public=True,
        publication__status="published",
    )
    if require_gazette_number:
        queryset = queryset.exclude(gazette_number="")
    return queryset.order_by("-publication__published_at", "-updated_at")


def public_open_appointments_queryset():
    return published_appointments_queryset().filter(status__in=OPEN_PUBLIC_APPOINTMENT_STATUSES)


def public_positions_queryset():
    return GovernmentPosition.objects.select_related(
        "current_holder",
    ).filter(
        is_public=True,
    ).order_by("title", "institution")


def public_vacant_positions_queryset():
    return public_positions_queryset().filter(is_vacant=True)


def public_officeholders_queryset():
    return PersonnelRecord.objects.filter(
        is_public=True,
        is_active_officeholder=True,
    ).order_by("full_name")


def apply_public_appointment_query_params(queryset, *, query_params):
    search = str(query_params.get("search", "") or "").strip()
    if search:
        queryset = queryset.filter(
            Q(position__title__icontains=search)
            | Q(position__institution__icontains=search)
            | Q(nominee__full_name__icontains=search)
            | Q(gazette_number__icontains=search)
            | Q(publication__publication_reference__icontains=search)
        )

    status = str(query_params.get("status", "") or "").strip()
    if status:
        queryset = queryset.filter(status=status)

    ordering = str(query_params.get("ordering", "") or "").strip()
    order_by = PUBLIC_APPOINTMENT_ORDERING_FIELDS.get(ordering)
    if order_by:
        queryset = queryset.order_by(order_by, "-updated_at")

    return queryset


def build_public_transparency_summary() -> dict:
    published_qs = published_appointments_queryset()
    last_published_at = (
        published_qs.exclude(publication__published_at__isnull=True)
        .values_list("publication__published_at", flat=True)
        .first()
    )

    return {
        "published_appointments": published_qs.count(),
        "open_public_appointments": public_open_appointments_queryset().count(),
        "public_positions": public_positions_queryset().count(),
        "vacant_public_positions": public_vacant_positions_queryset().count(),
        "active_public_officeholders": public_officeholders_queryset().count(),
        "last_published_at": last_published_at,
    }

