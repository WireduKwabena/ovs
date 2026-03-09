"""Social profile check orchestration for application cases."""

from __future__ import annotations

import logging
from typing import Any

from ai_ml_services.social.case_profiles import extract_case_social_profiles
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.billing.quotas import (
    VETTING_OPERATION_SOCIAL_PROFILE_CHECK,
    enforce_vetting_operation_quota,
    resolve_case_organization_id,
)

logger = logging.getLogger(__name__)


def run_case_social_profile_check(case: Any, *, actor=None) -> dict[str, Any]:
    """
    Run social profile checks for a vetting case and persist result.

    Returns a dict with ``success`` and either ``result`` or ``reason/error``.
    """
    case_id = str(getattr(case, "case_id", "") or "unknown")
    profiles, consent_provided = extract_case_social_profiles(case)

    if not profiles:
        return {
            "success": False,
            "case_id": case_id,
            "reason": "no_profiles",
            "message": "No social profiles available for this case.",
        }

    try:
        from ai_ml_services.service import check_social_profiles
        from apps.fraud.models import SocialProfileCheckResult
    except Exception as exc:  # pragma: no cover - optional app/dependency guards
        logger.warning(
            "Unable to run social profile check for case %s due to dependency error: %s",
            case_id,
            exc,
            exc_info=True,
        )
        return {
            "success": False,
            "case_id": case_id,
            "reason": "dependency_unavailable",
            "error": str(exc),
        }

    additional_usage = 1
    if SocialProfileCheckResult.objects.filter(application=case).exists():
        # Idempotent by case: refresh/recheck does not consume extra quota units.
        additional_usage = 0
    resolved_org_id = resolve_case_organization_id(case)
    quota_actor = actor if (resolved_org_id is None and getattr(actor, "is_authenticated", False)) else None
    try:
        enforce_vetting_operation_quota(
            operation=VETTING_OPERATION_SOCIAL_PROFILE_CHECK,
            user=quota_actor,
            organization_id=resolved_org_id,
            additional=additional_usage,
        )
    except DRFValidationError as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {"detail": exc.detail}
        return {
            "success": False,
            "case_id": case_id,
            "reason": "quota_enforced",
            "error": detail.get("detail") or "Quota enforcement blocked social profile check.",
            "quota": detail.get("quota"),
            "code": detail.get("code"),
        }

    try:
        result = check_social_profiles(
            profiles=profiles,
            consent_provided=consent_provided,
            case_id=case_id,
        )
    except Exception as exc:
        logger.warning(
            "Social profile check failed for case %s: %s",
            case_id,
            exc,
            exc_info=True,
        )
        return {
            "success": False,
            "case_id": case_id,
            "reason": "check_failed",
            "error": str(exc),
        }

    risk_level = str(result.get("risk_level", "high") or "high").strip().upper()
    if risk_level not in {"LOW", "MEDIUM", "HIGH"}:
        risk_level = "HIGH"

    recommendation = str(result.get("recommendation", "MANUAL_REVIEW") or "MANUAL_REVIEW").strip().upper()

    constraints = result.get("decision_constraints", [])
    if not isinstance(constraints, list):
        constraints = []

    checked_profiles = result.get("profiles", [])
    if not isinstance(checked_profiles, list):
        checked_profiles = []

    record, _ = SocialProfileCheckResult.objects.update_or_create(
        application=case,
        defaults={
            "consent_provided": bool(result.get("consent_provided", consent_provided)),
            "profiles_checked": int(result.get("profiles_checked", len(checked_profiles)) or 0),
            "overall_score": float(result.get("overall_score", 0.0) or 0.0),
            "risk_level": risk_level,
            "recommendation": recommendation,
            "automated_decision_allowed": bool(result.get("automated_decision_allowed", False)),
            "decision_constraints": constraints,
            "profiles": checked_profiles,
        },
    )

    return {
        "success": True,
        "case_id": case_id,
        "record_id": str(record.id),
        "result": result,
    }
