"""Reusable audit event helpers."""

from __future__ import annotations

import json
import logging
from typing import Any

from django.core.serializers.json import DjangoJSONEncoder

logger = logging.getLogger(__name__)


def request_ip_address(request: Any) -> str | None:
    """Extract caller IP, preferring X-Forwarded-For when present."""
    meta = getattr(request, "META", {}) or {}
    forwarded_for = str(meta.get("HTTP_X_FORWARDED_FOR", "") or "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or None

    remote_addr = str(meta.get("REMOTE_ADDR", "") or "").strip()
    return remote_addr or None


def request_user_agent(request: Any, max_length: int = 2000) -> str:
    """Return request user agent truncated to storage limit."""
    meta = getattr(request, "META", {}) or {}
    return str(meta.get("HTTP_USER_AGENT", "") or "")[:max_length]


def _json_sanitize(value: Any) -> Any:
    """Best-effort JSON sanitization for audit payloads."""
    try:
        json.dumps(value, cls=DjangoJSONEncoder)
        return value
    except TypeError:
        pass

    if isinstance(value, dict):
        return {str(key): _json_sanitize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_sanitize(item) for item in value]
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    return str(value)


def _normalize_changes(changes: Any) -> dict[str, Any]:
    """Normalize incoming changes payload into a JSON-safe dict."""
    sanitized = _json_sanitize(changes if changes is not None else {})
    if isinstance(sanitized, dict):
        return sanitized
    return {"value": sanitized}


def log_event(
    *,
    action: str = "other",
    entity_type: str,
    entity_id: str,
    changes: dict[str, Any] | None = None,
    request: Any | None = None,
    user: Any | None = None,
    admin_user: Any | None = None,
) -> bool:
    """
    Persist an audit log event.

    Returns:
        True if a row was persisted, False otherwise.
    """
    try:
        from apps.audit.models import AuditLog
    except Exception:
        return False

    actor = user
    if actor is None and request is not None:
        request_user = getattr(request, "user", None)
        if getattr(request_user, "is_authenticated", False):
            actor = request_user

    effective_admin_user = admin_user if admin_user is not None else actor

    try:
        AuditLog.objects.create(
            user=actor,
            admin_user=effective_admin_user,
            action=action,
            entity_type=str(entity_type or ""),
            entity_id=str(entity_id or ""),
            changes=_normalize_changes(changes),
            ip_address=request_ip_address(request) if request is not None else None,
            user_agent=request_user_agent(request) if request is not None else "",
        )
        return True
    except Exception:
        logger.warning(
            "Failed to persist audit event action=%s entity=%s:%s",
            action,
            entity_type,
            entity_id,
            exc_info=True,
        )
        return False
