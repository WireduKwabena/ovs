"""Heuristic interview engine aligned with current Django models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from django.db.models import Case, IntegerField, Value, When
from django.utils import timezone

from apps.applications.models import InterrogationFlag
from apps.interviews.models import InterviewSession


@dataclass(frozen=True)
class ResolutionAssessment:
    resolved: bool
    confidence: float
    resolution_summary: str
    credibility_assessment: str
    requires_follow_up: bool
    follow_up_angle: str
    red_flags: List[str]


class EnhancedInterviewEngine:
    """Generate flag-focused questions and heuristic resolution assessments."""

    SEVERITY_RANK = Case(
        When(severity="critical", then=Value(0)),
        When(severity="high", then=Value(1)),
        When(severity="medium", then=Value(2)),
        default=Value(3),
        output_field=IntegerField(),
    )

    def __init__(self, session: InterviewSession):
        self.session = session
        self.conversation_history = list(session.conversation_history or [])

    def _pending_flags(self):
        addressed_ids = set(
            self.session.flags_addressed.values_list("id", flat=True)
        )
        queryset = self.session.case.interrogation_flags.exclude(
            status__in=["resolved", "dismissed"]
        )
        if addressed_ids:
            queryset = queryset.exclude(id__in=addressed_ids)
        return queryset.order_by(self.SEVERITY_RANK, "created_at")

    def generate_next_question(self) -> Optional[Dict]:
        flag = self._pending_flags().first()
        if flag is None:
            return {
                "question": "Before we close, is there any detail you want to clarify about your submitted records?",
                "intent": "general_closure",
                "topic": "general",
                "target_flag_id": None,
                "reasoning": "No unresolved flags remain.",
            }
        return self._question_for_flag(flag)

    def _question_for_flag(self, flag: InterrogationFlag) -> Dict:
        title = (flag.title or "").strip()
        description = (flag.description or "").strip()
        prompt_basis = title or description or f"{flag.flag_type} issue"

        if flag.flag_type == "consistency_mismatch":
            question = (
                f"We identified a consistency issue: {prompt_basis}. "
                "Can you explain the discrepancy and what the correct record should be?"
            )
        elif flag.flag_type == "authenticity_concern":
            question = (
                f"Regarding document authenticity concerns ({prompt_basis}), "
                "can you provide context on where and how that document was issued?"
            )
        elif flag.flag_type == "missing_information":
            question = (
                f"We are missing required information ({prompt_basis}). "
                "Can you explain why it is missing and when you can provide it?"
            )
        else:
            question = (
                f"We need clarification on the following issue: {prompt_basis}. "
                "Please provide a clear and specific explanation."
            )

        self.session.flags_addressed.add(flag)
        if flag.status == "pending":
            flag.mark_addressed()

        return {
            "question": question,
            "intent": "resolve_flag",
            "topic": flag.flag_type,
            "target_flag_id": flag.id,
            "reasoning": f"Prioritized unresolved {flag.severity} severity flag.",
        }

    def analyze_response_for_flag_resolution(
        self,
        transcript: str,
        flag_id: int,
        nonverbal_data: Optional[Dict] = None,
    ) -> Dict:
        nonverbal_data = nonverbal_data or {}
        transcript = (transcript or "").strip()
        flag = InterrogationFlag.objects.get(id=flag_id)

        word_count = len(transcript.split())
        contains_detail_tokens = any(
            token in transcript.lower()
            for token in ("because", "since", "when", "issued", "document", "record")
        )
        deception_score = float(nonverbal_data.get("deception_score", 50) or 50)
        eye_contact = float(nonverbal_data.get("eye_contact_percentage", 50) or 50)

        base = min(100.0, word_count * 3.5)
        if contains_detail_tokens:
            base += 15.0
        base -= max(0.0, deception_score - 50.0) * 0.5
        base += max(0.0, eye_contact - 50.0) * 0.2
        confidence = max(0.0, min(100.0, base))

        resolved = confidence >= 65 and word_count >= 12
        requires_follow_up = not resolved or confidence < 78
        credibility = "high" if confidence >= 80 else ("medium" if confidence >= 60 else "low")

        if resolved:
            flag.status = "resolved"
            flag.resolved_at = timezone.now()
            flag.resolution_summary = "Issue appears clarified from interview response."
            flag.resolution_confidence = confidence
            flag.save(
                update_fields=[
                    "status",
                    "resolved_at",
                    "resolution_summary",
                    "resolution_confidence",
                ]
            )
        elif not requires_follow_up:
            flag.status = "unresolved"
            flag.resolution_summary = "Response did not provide enough evidence to resolve the issue."
            flag.save(update_fields=["status", "resolution_summary"])

        assessment = ResolutionAssessment(
            resolved=resolved,
            confidence=round(confidence, 2),
            resolution_summary=(
                "Response provides sufficient detail to address the flag."
                if resolved
                else "Response needs additional clarification before the flag can be closed."
            ),
            credibility_assessment=credibility,
            requires_follow_up=requires_follow_up,
            follow_up_angle=(
                "Request verifiable specifics (dates, issuer, and supporting documents)."
                if requires_follow_up
                else ""
            ),
            red_flags=(
                ["low_response_detail"] if word_count < 12 else []
            )
            + (["elevated_deception_signal"] if deception_score > 70 else []),
        )
        return assessment.__dict__

    def update_conversation_history(self, question: str, answer: str, nonverbal: Optional[Dict] = None) -> None:
        self.conversation_history.append(
            {
                "question": question,
                "answer": answer,
                "nonverbal": nonverbal or {},
                "timestamp": timezone.now().isoformat(),
            }
        )
        self.session.conversation_history = self.conversation_history
        self.session.save(update_fields=["conversation_history"])

    def get_interview_context(self) -> Dict:
        pending = self._pending_flags().count()
        return {
            "session_id": self.session.session_id,
            "pending_flags": pending,
            "questions_asked": self.session.total_questions_asked,
            "status": self.session.status,
        }

