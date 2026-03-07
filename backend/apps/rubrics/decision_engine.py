from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.audit.contracts import (
    VETTING_DECISION_OVERRIDE_RECORDED_EVENT,
    VETTING_DECISION_RECOMMENDATION_GENERATED_EVENT,
)
from apps.audit.events import log_event

try:  # pragma: no cover - optional app import guard
    from apps.fraud.models import SocialProfileCheckResult
except Exception:  # pragma: no cover - keep decision engine resilient in slim installs
    SocialProfileCheckResult = None  # type: ignore[assignment]

from .engine import RubricEvaluationEngine
from .models import RubricEvaluation, VettingDecisionOverride, VettingDecisionRecommendation


class VettingDecisionEngine:
    """Advisory-only decision layer that aggregates rubric + policy/evidence signals."""

    ENGINE_VERSION = "v1"

    @staticmethod
    def _normalize_list(value: Any) -> list[Any]:
        if isinstance(value, list):
            return value
        return []

    @staticmethod
    def _extract_ai_signal_snapshot(evaluation: RubricEvaluation) -> dict[str, Any]:
        if not isinstance(evaluation.criterion_scores, dict):
            return {}
        trace = evaluation.criterion_scores.get(RubricEvaluationEngine.TRACE_KEY)
        if not isinstance(trace, dict):
            return {}
        payload = trace.get("ai_signals")
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _background_checks_snapshot(case) -> dict[str, Any]:
        checks = case.background_checks.all() if hasattr(case, "background_checks") else []
        total = checks.count() if hasattr(checks, "count") else 0
        if total == 0:
            return {
                "total": 0,
                "pending": 0,
                "manual_review": 0,
                "failed": 0,
                "reject_recommendations": 0,
                "review_recommendations": 0,
            }
        return {
            "total": total,
            "pending": checks.filter(status__in=["pending", "submitted", "in_progress"]).count(),
            "manual_review": checks.filter(status="manual_review").count(),
            "failed": checks.filter(status="failed").count(),
            "reject_recommendations": checks.filter(recommendation="reject").count(),
            "review_recommendations": checks.filter(recommendation="review").count(),
        }

    @staticmethod
    def _social_snapshot(case) -> dict[str, Any]:
        if SocialProfileCheckResult is None:
            return {
                "available": False,
                "consent_provided": False,
                "automated_decision_allowed": False,
                "decision_constraints": [],
                "risk_level": "",
                "recommendation": "",
            }

        try:
            social = case.social_profile_result
        except Exception:
            social = None

        if social is None:
            return {
                "available": False,
                "consent_provided": False,
                "automated_decision_allowed": False,
                "decision_constraints": [],
                "risk_level": "",
                "recommendation": "",
            }
        return {
            "available": True,
            "consent_provided": bool(social.consent_provided),
            "automated_decision_allowed": bool(social.automated_decision_allowed),
            "decision_constraints": VettingDecisionEngine._normalize_list(social.decision_constraints),
            "risk_level": str(social.risk_level or ""),
            "recommendation": str(social.recommendation or ""),
        }

    @staticmethod
    def _evidence_snapshot(evaluation: RubricEvaluation) -> dict[str, Any]:
        case = evaluation.case
        background_checks = VettingDecisionEngine._background_checks_snapshot(case)
        social = VettingDecisionEngine._social_snapshot(case)
        return {
            "documents_uploaded": bool(case.documents_uploaded),
            "documents_verified": bool(case.documents_verified),
            "interview_completed": bool(case.interview_completed),
            "interview_score_present": evaluation.interview_score is not None,
            "unresolved_flags_count": int(evaluation.unresolved_flags_count or 0),
            "critical_flags_present": bool(evaluation.critical_flags_present),
            "background_checks": background_checks,
            "social_profile": social,
        }

    @staticmethod
    def _policy_snapshot(evaluation: RubricEvaluation) -> dict[str, Any]:
        rubric = evaluation.rubric
        return {
            "rubric_id": str(rubric.id),
            "passing_score": rubric.passing_score,
            "auto_approve_threshold": rubric.auto_approve_threshold,
            "auto_reject_threshold": rubric.auto_reject_threshold,
            "minimum_document_score": rubric.minimum_document_score,
            "maximum_fraud_score": rubric.maximum_fraud_score,
            "require_interview": bool(rubric.require_interview),
            "critical_flags_auto_fail": bool(rubric.critical_flags_auto_fail),
            "max_unresolved_flags": int(rubric.max_unresolved_flags or 0),
        }

    @staticmethod
    def _build_blocking_issues(
        *,
        evaluation: RubricEvaluation,
        evidence_snapshot: dict[str, Any],
        policy_snapshot: dict[str, Any],
    ) -> list[dict[str, Any]]:
        blockers: list[dict[str, Any]] = []

        def add_blocker(code: str, source: str, message: str, details: dict[str, Any] | None = None) -> None:
            payload = {
                "code": code,
                "severity": "blocking",
                "source": source,
                "message": message,
            }
            if details:
                payload["details"] = details
            blockers.append(payload)

        if not evidence_snapshot["documents_uploaded"]:
            add_blocker(
                code="documents_missing",
                source="evidence_completeness",
                message="No documents uploaded for vetting case.",
            )

        if not evidence_snapshot["documents_verified"]:
            add_blocker(
                code="documents_unverified",
                source="evidence_completeness",
                message="Documents are not fully verified.",
            )

        if policy_snapshot["require_interview"] and not evidence_snapshot["interview_completed"]:
            add_blocker(
                code="interview_missing",
                source="policy_rule",
                message="Interview is required before recommendation can proceed.",
            )

        if policy_snapshot["critical_flags_auto_fail"] and evidence_snapshot["critical_flags_present"]:
            add_blocker(
                code="critical_flags_detected",
                source="rubric_rule",
                message="Critical unresolved flags were detected.",
            )

        unresolved_flags_count = int(evidence_snapshot["unresolved_flags_count"])
        max_unresolved = int(policy_snapshot["max_unresolved_flags"])
        if unresolved_flags_count > max_unresolved:
            add_blocker(
                code="unresolved_flags_exceeded",
                source="rubric_rule",
                message="Unresolved flags exceed configured policy limit.",
                details={"unresolved_flags_count": unresolved_flags_count, "max_allowed": max_unresolved},
            )

        if isinstance(evaluation.criterion_scores, dict):
            for criterion_id, criterion_payload in evaluation.criterion_scores.items():
                if str(criterion_id).startswith("__"):
                    continue
                if not isinstance(criterion_payload, dict):
                    continue
                if criterion_payload.get("is_mandatory") and criterion_payload.get("passed") is False:
                    add_blocker(
                        code="mandatory_criterion_failed",
                        source="rubric_criterion",
                        message="One or more mandatory rubric criteria failed.",
                        details={
                            "criterion_id": str(criterion_id),
                            "criterion_name": criterion_payload.get("name"),
                        },
                    )

        background_checks = evidence_snapshot["background_checks"]
        if int(background_checks.get("reject_recommendations", 0)) > 0:
            add_blocker(
                code="background_check_reject",
                source="background_checks",
                message="A completed background check returned a reject recommendation.",
            )

        social = evidence_snapshot["social_profile"]
        if social.get("available") and social.get("consent_provided") is False:
            add_blocker(
                code="social_consent_missing",
                source="social_profile",
                message="Social profile consent is missing for available profile checks.",
            )

        return blockers

    @staticmethod
    def _build_warnings(
        *,
        evaluation: RubricEvaluation,
        evidence_snapshot: dict[str, Any],
        ai_signal_snapshot: dict[str, Any],
    ) -> list[dict[str, Any]]:
        warnings: list[dict[str, Any]] = []

        def add_warning(code: str, source: str, message: str, details: dict[str, Any] | None = None) -> None:
            payload = {
                "code": code,
                "severity": "warning",
                "source": source,
                "message": message,
            }
            if details:
                payload["details"] = details
            warnings.append(payload)

        if evaluation.requires_manual_review:
            add_warning(
                code="manual_review_required",
                source="rubric_output",
                message="Rubric evaluation requires manual review.",
                details={"reasons": list(evaluation.review_reasons or [])},
            )

        unresolved_flags_count = int(evidence_snapshot["unresolved_flags_count"])
        if unresolved_flags_count > 0:
            add_warning(
                code="unresolved_flags_present",
                source="case_flags",
                message="Case has unresolved flags.",
                details={"unresolved_flags_count": unresolved_flags_count},
            )

        background_checks = evidence_snapshot["background_checks"]
        if int(background_checks.get("pending", 0)) > 0:
            add_warning(
                code="background_checks_pending",
                source="background_checks",
                message="Some background checks are still pending.",
                details={"pending_count": int(background_checks.get("pending", 0))},
            )
        if int(background_checks.get("review_recommendations", 0)) > 0:
            add_warning(
                code="background_checks_review",
                source="background_checks",
                message="Background checks recommend manual review.",
                details={"review_count": int(background_checks.get("review_recommendations", 0))},
            )

        social = evidence_snapshot["social_profile"]
        constraints = VettingDecisionEngine._normalize_list(social.get("decision_constraints"))
        if constraints:
            add_warning(
                code="social_decision_constraints_present",
                source="social_profile",
                message="Social profile checks returned decision constraints.",
                details={"constraints": constraints},
            )

        if ai_signal_snapshot.get("flag_for_manual_review"):
            add_warning(
                code="advisory_ai_requested_manual_review",
                source="advisory_ai",
                message="AI advisory signal requested manual review.",
            )

        return warnings

    @staticmethod
    def _determine_recommendation_status(
        *,
        evaluation: RubricEvaluation,
        blocking_issues: list[dict[str, Any]],
    ) -> str:
        blocking_codes = {str(item.get("code", "")) for item in blocking_issues}
        if "critical_flags_detected" in blocking_codes or "background_check_reject" in blocking_codes:
            return "recommend_reject"
        if blocking_issues:
            return "recommend_manual_review"
        if evaluation.final_decision == "auto_rejected":
            return "recommend_reject"
        if evaluation.final_decision == "auto_approved" and not evaluation.requires_manual_review:
            return "recommend_approve"
        if evaluation.passes_threshold is True and not evaluation.requires_manual_review:
            return "recommend_approve"
        return "recommend_manual_review"

    @staticmethod
    def _build_explanation(
        *,
        evaluation: RubricEvaluation,
        recommendation_status: str,
        blocking_issues: list[dict[str, Any]],
        warnings: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if recommendation_status == "recommend_approve":
            headline = "Recommend approval based on current rubric and evidence checks."
        elif recommendation_status == "recommend_reject":
            headline = "Recommend rejection due to critical risk or policy blockers."
        else:
            headline = "Recommend manual review before any final human decision."

        return {
            "headline": headline,
            "summary": (
                "This recommendation is advisory only. "
                "Human decision-makers retain full authority for final determination."
            ),
            "score_context": {
                "total_weighted_score": evaluation.total_weighted_score,
                "passes_threshold": evaluation.passes_threshold,
                "rubric_decision": evaluation.final_decision,
            },
            "blocking_issue_count": len(blocking_issues),
            "warning_count": len(warnings),
        }

    @staticmethod
    def _build_decision_basis(
        *,
        evaluation: RubricEvaluation,
        evidence_snapshot: dict[str, Any],
        policy_snapshot: dict[str, Any],
        ai_signal_snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "rubric": {
                "evaluation_id": str(evaluation.id),
                "rubric_id": str(evaluation.rubric_id),
                "final_decision": evaluation.final_decision,
                "passes_threshold": evaluation.passes_threshold,
                "requires_manual_review": evaluation.requires_manual_review,
                "review_reasons": list(evaluation.review_reasons or []),
            },
            "evidence": evidence_snapshot,
            "policy": policy_snapshot,
            "ai_advisory": ai_signal_snapshot,
        }

    @classmethod
    def generate_recommendation(
        cls,
        *,
        evaluation: RubricEvaluation,
        actor=None,
        request=None,
    ) -> VettingDecisionRecommendation:
        evidence_snapshot = cls._evidence_snapshot(evaluation)
        policy_snapshot = cls._policy_snapshot(evaluation)
        ai_signal_snapshot = cls._extract_ai_signal_snapshot(evaluation)
        blocking_issues = cls._build_blocking_issues(
            evaluation=evaluation,
            evidence_snapshot=evidence_snapshot,
            policy_snapshot=policy_snapshot,
        )
        warnings = cls._build_warnings(
            evaluation=evaluation,
            evidence_snapshot=evidence_snapshot,
            ai_signal_snapshot=ai_signal_snapshot,
        )
        recommendation_status = cls._determine_recommendation_status(
            evaluation=evaluation,
            blocking_issues=blocking_issues,
        )
        explanation = cls._build_explanation(
            evaluation=evaluation,
            recommendation_status=recommendation_status,
            blocking_issues=blocking_issues,
            warnings=warnings,
        )
        decision_basis = cls._build_decision_basis(
            evaluation=evaluation,
            evidence_snapshot=evidence_snapshot,
            policy_snapshot=policy_snapshot,
            ai_signal_snapshot=ai_signal_snapshot,
        )

        with transaction.atomic():
            VettingDecisionRecommendation.objects.filter(case=evaluation.case, is_latest=True).update(is_latest=False)
            recommendation = VettingDecisionRecommendation.objects.create(
                case=evaluation.case,
                rubric_evaluation=evaluation,
                recommendation_status=recommendation_status,
                blocking_issues=blocking_issues,
                warnings=warnings,
                decision_basis=decision_basis,
                explanation=explanation,
                policy_snapshot=policy_snapshot,
                evidence_snapshot=evidence_snapshot,
                ai_signal_snapshot=ai_signal_snapshot,
                advisory_only=True,
                engine_version=cls.ENGINE_VERSION,
                generated_by=actor if getattr(actor, "is_authenticated", False) else None,
                is_latest=True,
            )

        if request is not None:
            log_event(
                request=request,
                action="create",
                entity_type="VettingDecisionRecommendation",
                entity_id=str(recommendation.id),
                changes={
                    "event": VETTING_DECISION_RECOMMENDATION_GENERATED_EVENT,
                    "case_id": str(evaluation.case_id),
                    "rubric_evaluation_id": str(evaluation.id),
                    "recommendation_status": recommendation.recommendation_status,
                    "blocking_issues_count": len(blocking_issues),
                    "warnings_count": len(warnings),
                    "engine_version": recommendation.engine_version,
                    "advisory_only": True,
                },
            )

        return recommendation

    @staticmethod
    def _ensure_recommendation_status(value: str) -> str:
        allowed = {choice[0] for choice in VettingDecisionRecommendation.RECOMMENDATION_CHOICES}
        normalized = str(value or "").strip()
        if normalized not in allowed:
            raise ValueError("Invalid recommendation_status for override.")
        return normalized

    @classmethod
    def record_human_override(
        cls,
        *,
        recommendation: VettingDecisionRecommendation,
        actor,
        overridden_recommendation_status: str,
        rationale: str,
        request=None,
    ) -> tuple[VettingDecisionRecommendation, VettingDecisionOverride]:
        normalized_status = cls._ensure_recommendation_status(overridden_recommendation_status)
        rationale_text = str(rationale or "").strip()
        if not rationale_text:
            raise ValueError("rationale is required for override.")

        with transaction.atomic():
            previous_status = recommendation.recommendation_status
            override = VettingDecisionOverride.objects.create(
                recommendation=recommendation,
                previous_recommendation_status=previous_status,
                overridden_recommendation_status=normalized_status,
                rationale=rationale_text,
                overridden_by=actor if getattr(actor, "is_authenticated", False) else None,
            )
            recommendation.recommendation_status = normalized_status
            decision_basis = dict(recommendation.decision_basis or {})
            decision_basis["human_override"] = {
                "previous_recommendation_status": previous_status,
                "overridden_recommendation_status": normalized_status,
                "overridden_by": str(getattr(actor, "id", "") or ""),
                "override_id": str(override.id),
            }
            recommendation.decision_basis = decision_basis
            recommendation.save(update_fields=["recommendation_status", "decision_basis", "updated_at"])

        if request is not None:
            log_event(
                request=request,
                action="update",
                entity_type="VettingDecisionRecommendation",
                entity_id=str(recommendation.id),
                changes={
                    "event": VETTING_DECISION_OVERRIDE_RECORDED_EVENT,
                    "override_id": str(override.id),
                    "previous_recommendation_status": override.previous_recommendation_status,
                    "overridden_recommendation_status": override.overridden_recommendation_status,
                    "has_rationale": bool(override.rationale),
                },
            )

        return recommendation, override
