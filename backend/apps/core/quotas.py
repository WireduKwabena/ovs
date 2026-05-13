from __future__ import annotations

from dataclasses import dataclass
from django.utils import timezone


VETTING_OPERATION_DOCUMENT_VERIFICATION = "document_verification"
VETTING_OPERATION_SOCIAL_PROFILE_CHECK = "social_profile_check"
VETTING_OPERATION_INTERVIEW_ANALYSIS = "interview_analysis"
VETTING_OPERATION_RUBRIC_EVALUATION = "rubric_evaluation"
VETTING_OPERATION_BACKGROUND_CHECK_SUBMISSION = "background_check_submission"


@dataclass(frozen=True)
class CandidateQuotaSnapshot:
    enforced: bool
    scope: str
    reason: str | None
    plan_id: str | None
    plan_name: str | None
    limit: int | None
    used: int
    remaining: int | None
    period_start: timezone.datetime
    period_end: timezone.datetime


def _month_window(now: timezone.datetime | None = None) -> tuple[timezone.datetime, timezone.datetime]:
    anchor = now or timezone.now()
    period_start = anchor.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if period_start.month == 12:
        period_end = period_start.replace(year=period_start.year + 1, month=1)
    else:
        period_end = period_start.replace(month=period_start.month + 1)
    return period_start, period_end


def resolve_case_organization_id(*, case=None, **kwargs) -> str | None:
    if case is None:
        case = kwargs.get("vetting_case")
    if case is None:
        return None
    organization_id = getattr(case, "organization_id", None)
    if organization_id:
        return str(organization_id)
    campaign = getattr(case, "campaign", None)
    campaign_org_id = getattr(campaign, "organization_id", None)
    return str(campaign_org_id) if campaign_org_id else None


def enforce_candidate_quota(*args, **kwargs) -> None:
    return None


def enforce_vetting_operation_quota(*args, **kwargs) -> None:
    return None


def enforce_organization_seat_quota(*args, **kwargs) -> None:
    return None


def enforce_membership_activation_seat_quota(*args, **kwargs) -> None:
    return None
