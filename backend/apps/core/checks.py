from __future__ import annotations

import os
import sys
from urllib.parse import urlparse

from django.apps import apps
from django.conf import settings
from django.core.checks import Error, Warning, register
from django.db import models


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
