from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.applications.models import VettingCase

from .models import RubricEvaluation, VettingRubric


class RubricEvaluationEngine:
    """Current-schema rubric evaluation engine."""

    TRACE_KEY = "__trace__"
    EXPLANATION_KEY = "__decision_explanation__"
    ENGINE_VERSION = "v2"

    def __init__(self, case: VettingCase, rubric: VettingRubric):
        self.case = case
        self.rubric = rubric

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        if parsed < 0 or parsed > 100:
            return None
        return parsed

    def _sanitize_ai_signals(self, ai_signals: Any) -> dict[str, Any]:
        if not isinstance(ai_signals, dict):
            return {"advisory_only": True, "criteria": {}, "source": ""}

        criteria_signals = {}
        raw_criteria = ai_signals.get("criteria")
        if isinstance(raw_criteria, dict):
            for raw_key, raw_payload in raw_criteria.items():
                key = str(raw_key).strip()
                if not key:
                    continue

                payload = raw_payload if isinstance(raw_payload, dict) else {"score": raw_payload}
                criteria_signals[key] = {
                    "score": self._safe_float(payload.get("score")),
                    "confidence": self._safe_float(payload.get("confidence")),
                    "flag_for_manual_review": bool(payload.get("flag_for_manual_review", False)),
                    "rationale": str(payload.get("rationale", "")).strip(),
                }

        source = str(ai_signals.get("source", "")).strip()[:100]
        summary = str(ai_signals.get("summary", "")).strip()[:600]
        top_level_flag = bool(ai_signals.get("flag_for_manual_review", False))

        return {
            "advisory_only": True,
            "source": source,
            "summary": summary,
            "criteria": criteria_signals,
            "flag_for_manual_review": top_level_flag,
        }

    def _lookup_advisory_signal(self, criterion_id: str, criterion_name: str, ai_signals: dict[str, Any]) -> dict[str, Any] | None:
        criteria_map = ai_signals.get("criteria", {})
        if not isinstance(criteria_map, dict):
            return None

        by_id = criteria_map.get(criterion_id)
        if isinstance(by_id, dict):
            return by_id

        normalized_name = criterion_name.strip().lower()
        for key, payload in criteria_map.items():
            if str(key).strip().lower() == normalized_name and isinstance(payload, dict):
                return payload
        return None

    def _resolve_criterion_score(self, criterion, evaluation: RubricEvaluation, baseline_average: float | None):
        if criterion.criteria_type == "document":
            return evaluation.document_authenticity_score, "document_authenticity_score"
        if criterion.criteria_type == "consistency":
            return evaluation.consistency_score, "consistency_score"
        if criterion.criteria_type == "interview":
            return evaluation.interview_score, "interview_score"
        if criterion.criteria_type in {"behavioral", "technical", "custom"}:
            return baseline_average, "baseline_average"
        return baseline_average, "baseline_average"

    def _build_decision_explanation(self, evaluation: RubricEvaluation, trace_payload: dict[str, Any]) -> dict[str, Any]:
        if evaluation.final_decision == "auto_approved":
            headline = "Auto-approved by configured rubric thresholds."
        elif evaluation.final_decision == "auto_rejected":
            headline = "Auto-rejected by configured rubric thresholds/risk rules."
        else:
            headline = "Manual reviewer decision required."

        score_statement = (
            f"Legacy weighted score {evaluation.total_weighted_score} "
            f"(threshold {evaluation.rubric.passing_score})."
        )
        normalized_score = trace_payload.get("scoring", {}).get("normalized_score")
        if normalized_score is not None:
            score_statement += f" Normalized score {round(normalized_score, 2)}."

        decision_basis = [
            f"passes_threshold={evaluation.passes_threshold}",
            f"requires_manual_review={evaluation.requires_manual_review}",
            f"unresolved_flags={evaluation.unresolved_flags_count}",
        ]
        if evaluation.critical_flags_present:
            decision_basis.append("critical_flags_present=True")

        return {
            "headline": headline,
            "score_statement": score_statement,
            "decision_basis": decision_basis,
            "review_reasons": list(evaluation.review_reasons or []),
            "advisory_only_ai": True,
        }

    def _build_trace_payload(self, evaluation: RubricEvaluation, ai_signals: dict[str, Any], criteria_scores: dict[str, Any]):
        component_breakdown = evaluation.get_component_breakdown()
        passed_criteria = 0
        failed_criteria = 0
        missing_criteria = 0
        total_criteria_weight = 0
        present_criteria_weight = 0

        for criterion_entry in criteria_scores.values():
            if not isinstance(criterion_entry, dict):
                continue
            if criterion_entry.get("score") is None:
                missing_criteria += 1
                continue
            criterion_weight = int(criterion_entry.get("weight") or 0)
            total_criteria_weight += criterion_weight
            present_criteria_weight += criterion_weight
            if criterion_entry.get("passed") is True:
                passed_criteria += 1
            elif criterion_entry.get("passed") is False:
                failed_criteria += 1

        return {
            "engine_version": self.ENGINE_VERSION,
            "generated_at": timezone.now().isoformat(),
            "provenance": {
                "case_id": str(self.case.id),
                "rubric_id": str(self.rubric.id),
            },
            "scoring": {
                "legacy_total_weighted_score": evaluation.total_weighted_score,
                "normalized_score": component_breakdown.get("normalized_score"),
                "available_component_weight": component_breakdown.get("available_weight"),
                "passing_threshold": self.rubric.passing_score,
                "auto_approve_threshold": self.rubric.auto_approve_threshold,
                "auto_reject_threshold": self.rubric.auto_reject_threshold,
                "criteria_weight_present": present_criteria_weight,
                "criteria_weight_total": total_criteria_weight,
            },
            "components": component_breakdown.get("components", {}),
            "criteria_summary": {
                "total": len(criteria_scores),
                "passed": passed_criteria,
                "failed": failed_criteria,
                "missing_scores": missing_criteria,
            },
            "decision": {
                "final_decision": evaluation.final_decision,
                "passes_threshold": evaluation.passes_threshold,
                "requires_manual_review": evaluation.requires_manual_review,
                "review_reasons": list(evaluation.review_reasons or []),
            },
            "ai_signals": ai_signals,
            "events": [],
        }

    def evaluate(self, evaluated_by=None, ai_signals: dict[str, Any] | None = None) -> RubricEvaluation:
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
        evaluation.requires_manual_review = False

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

        sanitized_ai_signals = self._sanitize_ai_signals(ai_signals)
        criteria_scores = {}
        for criterion in self.rubric.criteria.all().order_by("display_order", "id"):
            score, score_source = self._resolve_criterion_score(criterion, evaluation, baseline_average)
            criterion_id = str(criterion.id)
            advisory_signal = self._lookup_advisory_signal(
                criterion_id=criterion_id,
                criterion_name=criterion.name,
                ai_signals=sanitized_ai_signals,
            )
            weighted_contribution = None
            if score is not None:
                weighted_contribution = score * criterion.weight / 100

            criterion_payload = {
                "name": criterion.name,
                "criteria_type": criterion.criteria_type,
                "score": score,
                "score_source": score_source,
                "weight": criterion.weight,
                "weighted_contribution": weighted_contribution,
                "minimum_score": criterion.minimum_score,
                "is_mandatory": criterion.is_mandatory,
                "scoring_method": criterion.scoring_method,
                "passed": (
                    True
                    if criterion.minimum_score is None
                    else (score is not None and score >= criterion.minimum_score)
                ),
            }
            if advisory_signal is not None:
                criterion_payload["advisory_ai_signal"] = advisory_signal
                if advisory_signal.get("flag_for_manual_review"):
                    evaluation.requires_manual_review = True
                    evaluation._add_review_reason(
                        f"AI advisory requested manual review for criterion '{criterion.name}'."
                    )

            if criterion.is_mandatory and criterion_payload["passed"] is False:
                evaluation.requires_manual_review = True
                evaluation._add_review_reason(f"Mandatory criterion failed: {criterion.name}")

            criteria_scores[criterion_id] = criterion_payload

        if sanitized_ai_signals.get("flag_for_manual_review"):
            evaluation.requires_manual_review = True
            evaluation._add_review_reason("AI advisory requested manual review.")

        evaluation.criterion_scores = criteria_scores
        evaluation.status = "completed"
        evaluation.evaluated_at = timezone.now()
        evaluation.evaluated_by = evaluated_by
        evaluation.save()
        evaluation.refresh_from_db()

        trace_payload = self._build_trace_payload(
            evaluation=evaluation,
            ai_signals=sanitized_ai_signals,
            criteria_scores=criteria_scores,
        )
        explanation_payload = self._build_decision_explanation(evaluation=evaluation, trace_payload=trace_payload)

        recommendation = [explanation_payload["headline"]]
        if evaluation.requires_manual_review:
            recommendation.append("Manual review required due to rules/flags/advisory signals.")

        summary = (
            f"Rubric evaluation complete. Score={evaluation.total_weighted_score}, "
            f"decision={evaluation.final_decision}, unresolved_flags={evaluation.unresolved_flags_count}. "
            f"NormalizedScore={trace_payload.get('scoring', {}).get('normalized_score')}."
        )
        criteria_scores_with_metadata = dict(criteria_scores)
        criteria_scores_with_metadata[self.TRACE_KEY] = trace_payload
        criteria_scores_with_metadata[self.EXPLANATION_KEY] = explanation_payload

        RubricEvaluation.objects.filter(pk=evaluation.pk).update(
            recommendations=" ".join(recommendation),
            evaluation_summary=summary,
            criterion_scores=criteria_scores_with_metadata,
        )
        evaluation.refresh_from_db()
        return evaluation
