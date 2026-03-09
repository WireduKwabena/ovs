import logging

from celery import shared_task
from django.contrib.auth import get_user_model

from apps.applications.models import VettingCase
from apps.billing.quotas import (
    VETTING_OPERATION_RUBRIC_EVALUATION,
    enforce_vetting_operation_quota,
    resolve_case_organization_id,
)

from .decision_engine import VettingDecisionEngine
from .engine import RubricEvaluationEngine
from .models import RubricEvaluation, VettingRubric

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=1)
def evaluate_case_with_rubric(self, case_id: int, rubric_id: int, evaluator_id: int | None = None):
    try:
        case = VettingCase.objects.get(id=case_id)
        rubric = VettingRubric.objects.get(id=rubric_id)
    except (VettingCase.DoesNotExist, VettingRubric.DoesNotExist) as exc:
        return {"success": False, "error": str(exc)}

    evaluated_by = None
    if evaluator_id:
        user_model = get_user_model()
        try:
            evaluated_by = user_model.objects.get(id=evaluator_id)
        except user_model.DoesNotExist:
            logger.warning("Rubric evaluation requested with missing evaluator_id=%s", evaluator_id)
        except (TypeError, ValueError):
            logger.warning("Rubric evaluation requested with invalid evaluator_id=%s", evaluator_id)

    existing_evaluation = RubricEvaluation.objects.filter(case=case).exists()
    resolved_org_id = resolve_case_organization_id(case, actor=evaluated_by)
    fallback_actor = evaluated_by
    if fallback_actor is None and resolved_org_id is None:
        fallback_actor = getattr(case, "assigned_to", None) or getattr(case, "applicant", None)
    quota_actor = fallback_actor if (resolved_org_id is None and getattr(fallback_actor, "is_authenticated", False)) else None
    enforce_vetting_operation_quota(
        operation=VETTING_OPERATION_RUBRIC_EVALUATION,
        user=quota_actor,
        organization_id=resolved_org_id,
        additional=0 if existing_evaluation else 1,
    )

    evaluation = RubricEvaluationEngine(case=case, rubric=rubric).evaluate(evaluated_by=evaluated_by)
    recommendation = VettingDecisionEngine.generate_recommendation(
        evaluation=evaluation,
        actor=evaluated_by,
        request=None,
    )
    return {
        "success": True,
        "evaluation_id": evaluation.id,
        "total_weighted_score": evaluation.total_weighted_score,
        "final_decision": evaluation.final_decision,
        "requires_manual_review": evaluation.requires_manual_review,
        "decision_recommendation_id": recommendation.id,
        "decision_recommendation_status": recommendation.recommendation_status,
    }


@shared_task(bind=True, max_retries=1)
def auto_assign_rubric(self, case_id: int):
    try:
        case = VettingCase.objects.get(id=case_id)
    except VettingCase.DoesNotExist:
        return {"success": False, "error": f"Case {case_id} not found"}

    rubric = VettingRubric.objects.filter(is_active=True, is_default=True).order_by("-updated_at").first()
    if rubric is None:
        rubric = VettingRubric.objects.filter(is_active=True).order_by("-updated_at").first()
    if rubric is None:
        return {"success": False, "error": "No active rubric available"}

    return evaluate_case_with_rubric.run(case.id, rubric.id)
