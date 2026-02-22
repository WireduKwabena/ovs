"""Shared auth/security helpers."""

from __future__ import annotations

import secrets

from django.conf import settings


def has_valid_service_token(request) -> bool:
    """
    Validate service-to-service auth token from request headers.

    Accepted header formats:
    - ``X-Service-Token: <token>``
    - ``Authorization: Bearer <token>``
    """
    expected = str(getattr(settings, "SERVICE_TOKEN", "") or "")
    if not expected:
        return False

    provided = (
        request.headers.get("X-Service-Token")
        or request.META.get("HTTP_X_SERVICE_TOKEN")
        or ""
    ).strip()

    if not provided:
        auth_header = (
            request.headers.get("Authorization")
            or request.META.get("HTTP_AUTHORIZATION")
            or ""
        ).strip()
        if auth_header.lower().startswith("bearer "):
            provided = auth_header[7:].strip()

    if not provided:
        return False
    return secrets.compare_digest(str(provided), expected)
