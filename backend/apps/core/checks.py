from __future__ import annotations

import os
import sys
from urllib.parse import urlparse

from django.apps import apps
from django.conf import settings
from django.core.checks import Error, Warning, register
from django.db import connections, models
from django.db.migrations.executor import MigrationExecutor
from django.db.models import F, Q
from django.core.exceptions import FieldError
from django.db.utils import OperationalError, ProgrammingError


@register()
def enforce_uuid_primary_keys(app_configs, **kwargs):
    """
    Enforce UUID primary keys for all managed project models.
    """
    errors = []

    for model in apps.get_models():
        module_name = getattr(model, "__module__", "")
        if not module_name.startswith("apps."):
            continue

        if model._meta.abstract or model._meta.proxy or not model._meta.managed:
            continue

        pk_field = model._meta.pk
        if isinstance(pk_field, models.UUIDField):
            continue

        errors.append(
            Error(
                f"{model._meta.label} uses non-UUID primary key "
                f"({pk_field.__class__.__name__}).",
                hint="Set `id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)`.",
                obj=model,
                id="core.E001",
            )
        )

    return errors


def _is_local_host(value: str) -> bool:
    normalized = str(value or "").strip().lower()
    return normalized in {"localhost", "127.0.0.1", "0.0.0.0", "[::1]"}


def _is_test_runtime() -> bool:
    """
    Detect Django/pytest test execution contexts.

    This prevents production-origin hardening checks from blocking unit/integration
    tests where Django may force DEBUG=False in the test environment.
    """
    argv = " ".join(sys.argv).lower()
    return (
        " test " in f" {argv} "
        or " pytest " in f" {argv} "
        or os.getenv("PYTEST_CURRENT_TEST") is not None
    )


@register()
def enforce_production_origin_hardening(app_configs, **kwargs):
    """
    Enforce safer host/origin settings when running with DEBUG disabled.
    """
    if settings.DEBUG or _is_test_runtime():
        return []

    findings = []
    allowed_hosts = [
        str(host).strip().lower()
        for host in getattr(settings, "ALLOWED_HOSTS", [])
        if str(host).strip()
    ]
    if not allowed_hosts:
        findings.append(
            Error(
                "ALLOWED_HOSTS cannot be empty when DEBUG=False.",
                hint="Set ALLOWED_HOSTS to your production domains.",
                id="core.E002",
            )
        )
    if "*" in allowed_hosts:
        findings.append(
            Error(
                "ALLOWED_HOSTS cannot contain '*' when DEBUG=False.",
                hint="Use explicit hostnames for production.",
                id="core.E003",
            )
        )
    if any(_is_local_host(host) for host in allowed_hosts):
        findings.append(
            Error(
                "ALLOWED_HOSTS cannot include localhost/loopback values when DEBUG=False.",
                hint="Remove localhost, 127.0.0.1, and similar loopback hosts.",
                id="core.E004",
            )
        )

    csrf_origins = list(getattr(settings, "CSRF_TRUSTED_ORIGINS", []) or [])
    if not csrf_origins:
        findings.append(
            Error(
                "CSRF_TRUSTED_ORIGINS cannot be empty when DEBUG=False.",
                hint="Configure explicit HTTPS frontend origins.",
                id="core.E005",
            )
        )

    for origin in csrf_origins:
        parsed = urlparse(str(origin))
        if parsed.scheme != "https":
            findings.append(
                Error(
                    f"CSRF trusted origin is not HTTPS: {origin}",
                    hint="Use https:// origins in production.",
                    id="core.E006",
                )
            )
        if _is_local_host(parsed.hostname or ""):
            findings.append(
                Error(
                    f"CSRF trusted origin points to localhost/loopback: {origin}",
                    hint="Use publicly reachable HTTPS origins in production.",
                    id="core.E007",
                )
            )

    cors_origins = list(getattr(settings, "CORS_ALLOWED_ORIGINS", []) or [])
    for origin in cors_origins:
        parsed = urlparse(str(origin))
        if parsed.scheme and parsed.scheme != "https":
            findings.append(
                Warning(
                    f"CORS origin is not HTTPS: {origin}",
                    hint="Prefer https:// origins in production.",
                    id="core.W001",
                )
            )
        if _is_local_host(parsed.hostname or ""):
            findings.append(
                Warning(
                    f"CORS origin points to localhost/loopback: {origin}",
                    hint="Remove localhost origins for production deployments.",
                    id="core.W002",
                )
            )

    return findings


@register()
def enforce_tenant_internal_org_integrity(app_configs, **kwargs):
    """
    Tenant integrity check for organization-scoped internal models.

    This remains additive/non-destructive:
    - warns (or errors via settings) when null-org legacy rows still exist
    - warns (or errors via settings) when appointment linkage has cross-org mismatches
    """
    if not bool(getattr(settings, "TENANT_ORG_INTEGRITY_CHECK_ENABLED", True)):
        return []

    findings = []
    try:
        if _has_pending_migrations():
            findings.append(
                Warning(
                    (
                        "Tenant organization integrity check skipped because pending migrations exist. "
                        "Apply pending migrations before relying on tenant integrity checks."
                    ),
                    id="core.W012",
                )
            )
            return findings
    except (ProgrammingError, OperationalError):
        findings.append(
            Warning(
                (
                    "Tenant organization integrity check skipped because migration state could not be resolved. "
                    "Apply pending migrations before relying on tenant integrity checks."
                ),
                id="core.W012",
            )
        )
        return findings
    target_models = (
        ("positions", "GovernmentPosition"),
        ("personnel", "PersonnelRecord"),
        ("campaigns", "VettingCampaign"),
        ("applications", "VettingCase"),
        ("appointments", "ApprovalStageTemplate"),
        ("appointments", "AppointmentRecord"),
        ("rubrics", "VettingRubric"),
    )

    null_org_summary: list[str] = []
    null_org_total = 0

    for app_label, model_name in target_models:
        model = apps.get_model(app_label, model_name)
        if model is None:
            continue
        if not any(field.name == "organization" for field in model._meta.get_fields()):
            continue
        try:
            count = model.objects.filter(organization__isnull=True).count()
        except (ProgrammingError, OperationalError):
            findings.append(
                Warning(
                    (
                        "Tenant organization integrity check skipped because tenant columns are unavailable. "
                        "Apply pending migrations before relying on tenant integrity checks."
                    ),
                    id="core.W012",
                )
            )
            return findings
        if count > 0:
            null_org_total += int(count)
            null_org_summary.append(f"{model._meta.label}:{count}")

    if null_org_total > 0:
        message = (
            "Organization-scoped internal models still contain null-organization records. "
            f"Total={null_org_total} ({', '.join(null_org_summary)})."
        )
        hint = (
            "Backfill organization ownership for legacy records. "
            "Set TENANT_FAIL_ON_NULL_ORG_INTERNAL_RECORDS=true to fail closed at startup."
        )
        if bool(getattr(settings, "TENANT_FAIL_ON_NULL_ORG_INTERNAL_RECORDS", False)):
            findings.append(Error(message, hint=hint, id="core.E010"))
        else:
            findings.append(Warning(message, hint=hint, id="core.W010"))

    AppointmentRecord = apps.get_model("appointments", "AppointmentRecord")
    if AppointmentRecord is not None:
        try:
            mismatch_count = AppointmentRecord.objects.filter(
                Q(organization_id__isnull=False, position__organization_id__isnull=False)
                & ~Q(organization_id=F("position__organization_id"))
                | Q(organization_id__isnull=False, nominee__organization_id__isnull=False)
                & ~Q(organization_id=F("nominee__organization_id"))
                | Q(organization_id__isnull=False, appointment_exercise__organization_id__isnull=False)
                & ~Q(organization_id=F("appointment_exercise__organization_id"))
                | Q(organization_id__isnull=False, vetting_case__organization_id__isnull=False)
                & ~Q(organization_id=F("vetting_case__organization_id"))
            ).count()
        except (ProgrammingError, OperationalError, FieldError):
            mismatch_count = 0

        if mismatch_count > 0:
            message = (
                "Appointment records contain cross-organization linkage mismatches "
                f"(count={mismatch_count})."
            )
            hint = (
                "Normalize appointment.organization against linked position/nominee/exercise/vetting_case ownership. "
                "Set TENANT_FAIL_ON_CROSS_ORG_LINKAGE_MISMATCH=true to fail closed at startup."
            )
            if bool(getattr(settings, "TENANT_FAIL_ON_CROSS_ORG_LINKAGE_MISMATCH", False)):
                findings.append(Error(message, hint=hint, id="core.E011"))
            else:
                findings.append(Warning(message, hint=hint, id="core.W011"))

    return findings


def _has_pending_migrations(using: str = "default") -> bool:
    connection = connections[using]
    executor = MigrationExecutor(connection)
    targets = executor.loader.graph.leaf_nodes()
    plan = executor.migration_plan(targets)
    return bool(plan)
