from __future__ import annotations

from django.utils import timezone

from apps.applications.models import VettingCase

from .models import RubricEvaluation, VettingRubric


class RubricEvaluationEngine:
    """Current-schema rubric evaluation engine."""

    def __init__(self, case: VettingCase, rubric: VettingRubric):
        self.case = case
        self.rubric = rubric

    def evaluate(self, evaluated_by=None) -> RubricEvaluation:
        evaluation, _ = RubricEvaluation.objects.get_or_create(
            case=self.case,
            defaults={"rubric": self.rubric},
        )
        evaluation.rubric = self.rubric
        evaluation.status = "in_progress"

        # Snapshot case scores into rubric inputs.
        evaluation.document_authenticity_score = self.case.document_authenticity_score
        evaluation.consistency_score = self.case.consistency_score
        evaluation.fraud_risk_score = self.case.fraud_risk_score
        evaluation.interview_score = self.case.interview_score

        unresolved_flags = self.case.interrogation_flags.exclude(status__in=["resolved", "dismissed"])
        evaluation.unresolved_flags_count = unresolved_flags.count()
        evaluation.critical_flags_present = unresolved_flags.filter(severity="critical").exists()
        evaluation.review_reasons = []

        baseline_inputs = [
            value
            for value in [
                evaluation.document_authenticity_score,
                evaluation.consistency_score,
                (100 - evaluation.fraud_risk_score) if evaluation.fraud_risk_score is not None else None,
                evaluation.interview_score,
            ]
            if value is not None
        ]
        baseline_average = sum(baseline_inputs) / len(baseline_inputs) if baseline_inputs else None

        criteria_scores = {}
        for criterion in self.rubric.criteria.all().order_by("display_order", "id"):
            if criterion.criteria_type == "document":
                score = evaluation.document_authenticity_score
            elif criterion.criteria_type == "consistency":
                score = evaluation.consistency_score
            elif criterion.criteria_type == "interview":
                score = evaluation.interview_score
            else:
                score = baseline_average

            criteria_scores[str(criterion.id)] = {
                "name": criterion.name,
                "criteria_type": criterion.criteria_type,
                "score": score,
                "weight": criterion.weight,
                "minimum_score": criterion.minimum_score,
                "is_mandatory": criterion.is_mandatory,
                "passed": (
                    True
                    if criterion.minimum_score is None
                    else (score is not None and score >= criterion.minimum_score)
                ),
            }

        evaluation.criterion_scores = criteria_scores
        evaluation.status = "completed"
        evaluation.evaluated_at = timezone.now()
        evaluation.evaluated_by = evaluated_by
        evaluation.save()
        evaluation.refresh_from_db()

        recommendation = []
        if evaluation.final_decision == "auto_approved":
            recommendation.append("Auto-approved by rubric threshold.")
        elif evaluation.final_decision == "auto_rejected":
            recommendation.append("Auto-rejected by rubric threshold.")
        else:
            recommendation.append("Manual HR decision required.")
        if evaluation.requires_manual_review:
            recommendation.append("Manual review required due to rules/flags.")

        summary = (
            f"Rubric evaluation complete. Score={evaluation.total_weighted_score}, "
            f"decision={evaluation.final_decision}, unresolved_flags={evaluation.unresolved_flags_count}."
        )
        RubricEvaluation.objects.filter(pk=evaluation.pk).update(
            recommendations=" ".join(recommendation),
            evaluation_summary=summary,
        )
        evaluation.refresh_from_db()
        return evaluation
