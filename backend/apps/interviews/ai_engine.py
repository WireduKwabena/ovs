from __future__ import annotations

from typing import Any

from .models import DynamicInterviewSession
from .services.enhanced_engine import EnhancedInterviewEngine


class DynamicInterviewEngine:
    """
    Backward-compatible wrapper around the current interview engine.

    Kept to avoid breaking legacy imports that still expect
    ``apps.interviews.ai_engine.DynamicInterviewEngine``.
    """

    def __init__(self, session: DynamicInterviewSession):
        self.session = session
        self._engine = EnhancedInterviewEngine(session)
        self.conversation_history = list(session.conversation_history or [])

    def _build_context(self) -> dict[str, Any]:
        return self._engine.get_interview_context()

    def _format_conversation_history(self, history) -> str:
        if not history:
            return "No previous conversation."
        lines: list[str] = []
        for exchange in history:
            question = exchange.get("question", "")
            answer = exchange.get("answer", "")
            lines.append(f"Q: {question}")
            lines.append(f"A: {answer}")
        return "\n".join(lines)

    def should_end_interview(self) -> bool:
        return self.session.total_questions_asked >= self.session.max_questions

    def _ai_should_end_decision(self) -> bool:
        return self.should_end_interview()

    def generate_next_question(self):
        if self.should_end_interview():
            return None
        return self._engine.generate_next_question()

    def analyze_response(self, transcript, question_intent):
        text = (transcript or "").strip()
        words = [w for w in text.split() if w]
        quality = max(0.0, min(100.0, 30.0 + (len(words) * 4.0)))
        relevance_bonus = 10.0 if question_intent in {"resolve_flag", "verification"} else 0.0
        relevance = max(0.0, min(100.0, quality + relevance_bonus))
        sentiment = "neutral"
        if any(token in text.lower() for token in ("yes", "clearly", "verified", "confirmed")):
            sentiment = "confident"
        if any(token in text.lower() for token in ("not sure", "unknown", "can't recall", "maybe")):
            sentiment = "nervous"

        return {
            "key_points": words[:8],
            "inconsistencies": [],
            "clarifications_needed": [] if len(words) >= 10 else ["Provide more specific details."],
            "quality_score": round(quality, 2),
            "relevance_score": round(relevance, 2),
            "sentiment": sentiment,
            "confidence_level": round(max(0.0, min(100.0, relevance - 5.0)), 2),
            "red_flags": [] if len(words) >= 8 else ["insufficient_detail"],
        }
