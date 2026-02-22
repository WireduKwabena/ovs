from __future__ import annotations

from typing import Iterable


INTERVIEW_PROGRESS_STATUSES: frozenset[str] = frozenset(
    {
        "pending",
        "document_upload",
        "document_analysis",
        "interview_scheduled",
        "interview_in_progress",
    }
)


def sync_case_interview_outcome(
    *,
    case,
    interview_score: float | None,
    transition_statuses: Iterable[str] = INTERVIEW_PROGRESS_STATUSES,
) -> list[str]:
    """
    Persist canonical case updates after interview scoring.

    Returns a list of updated fields, or an empty list when no update is required.
    """
    updated_fields: list[str] = []

    if not case.interview_completed:
        case.interview_completed = True
        updated_fields.append("interview_completed")

    if interview_score is not None and case.interview_score != interview_score:
        case.interview_score = interview_score
        updated_fields.append("interview_score")

    if case.status in set(transition_statuses) and case.status != "under_review":
        case.status = "under_review"
        updated_fields.append("status")

    if not updated_fields:
        return []

    updated_fields.append("updated_at")
    case.save(update_fields=updated_fields)
    return updated_fields
