"""Interview decision engine for AI-led vetting interviews."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class InterviewFlag:
    """Simple in-memory representation of a flag under investigation."""

    id: Any
    context: str
    severity: str = "medium"
    status: str = "pending"


class EnhancedInterviewEngine:
    """Generate and adapt interview questions from session context and flags."""

    def __init__(self, session_data: Dict[str, Any]):
        self.session_data = session_data or {}
        self.conversation_history: List[Dict[str, Any]] = []
        self.questions_asked = 0
        self.max_questions = int(self.session_data.get("max_questions", 12))
        self.min_questions = int(self.session_data.get("min_questions", 5))
        self.flags = self._normalize_flags(self.session_data.get("interrogation_flags", []))

    def _normalize_flags(self, flags: List[Dict[str, Any]]) -> List[InterviewFlag]:
        normalized: List[InterviewFlag] = []
        for index, flag in enumerate(flags):
            normalized.append(
                InterviewFlag(
                    id=flag.get("id", index + 1),
                    context=flag.get("context") or flag.get("description", ""),
                    severity=flag.get("severity", "medium"),
                    status=flag.get("status", "pending"),
                )
            )
        return normalized

    def _next_pending_flag(self) -> Optional[InterviewFlag]:
        for flag in self.flags:
            if flag.status in {"pending", "addressed"}:
                return flag
        return None

    def generate_next_question(self) -> Optional[Dict[str, Any]]:
        """Generate the next interview question or return None when complete."""
        if self.questions_asked >= self.max_questions:
            return None

        pending_flag = self._next_pending_flag()
        if pending_flag is None and self.questions_asked >= self.min_questions:
            return None

        self.questions_asked += 1
        if pending_flag is not None:
            return {
                "question": (
                    "Please clarify this item from your submission: "
                    f"{pending_flag.context}. Could you provide specific details?"
                ),
                "intent": "resolve_flag",
                "target_flag_id": pending_flag.id,
                "reasoning": f"Targeting unresolved {pending_flag.severity} flag",
            }

        generic_questions = [
            "Can you summarize your recent role and key responsibilities?",
            "What should we verify first from your submitted documents?",
            "Walk me through any gap in your timeline and what happened.",
        ]
        question = generic_questions[(self.questions_asked - 1) % len(generic_questions)]
        return {
            "question": question,
            "intent": "general_clarification",
            "target_flag_id": None,
            "reasoning": "Collecting baseline interview evidence",
        }

    def analyze_response_for_flag_resolution(
        self,
        transcript: str,
        flag_id: Any,
        nonverbal_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Heuristic resolution check for current flag."""
        if flag_id is None:
            return {"resolved": False, "reason": "No active flag"}

        transcript = (transcript or "").strip()
        nonverbal_data = nonverbal_data or {}
        evasive_markers = {"not sure", "can't remember", "no comment", "unknown"}
        lower_text = transcript.lower()

        likely_evasive = any(marker in lower_text for marker in evasive_markers)
        length_ok = len(transcript.split()) >= 10
        confidence = float(nonverbal_data.get("confidence_score", 50))
        resolved = length_ok and not likely_evasive and confidence >= 40

        for flag in self.flags:
            if flag.id == flag_id:
                flag.status = "resolved" if resolved else "addressed"
                break

        return {
            "resolved": resolved,
            "flag_id": flag_id,
            "confidence_score": confidence,
            "reason": "Response appears specific and non-evasive"
            if resolved
            else "Insufficient detail or low confidence signals",
        }

    def update_conversation_history(
        self,
        question: str,
        answer: str,
        nonverbal: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.conversation_history.append(
            {
                "question": question,
                "answer": answer,
                "nonverbal": nonverbal or {},
            }
        )

    def get_interview_context(self) -> Dict[str, Any]:
        unresolved = [flag for flag in self.flags if flag.status != "resolved"]
        return {
            "questions_asked": self.questions_asked,
            "max_questions": self.max_questions,
            "unresolved_flags": len(unresolved),
            "history_size": len(self.conversation_history),
        }
