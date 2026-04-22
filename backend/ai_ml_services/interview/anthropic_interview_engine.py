"""Claude-powered interview engine for AI-led vetting sessions."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from django.conf import settings

logger = logging.getLogger(__name__)

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", re.DOTALL)
_JSON_INLINE_RE = re.compile(r"\{[\s\S]*\}", re.DOTALL)


def _extract_json(text: str) -> dict:
    """Robustly extract a JSON object from a Claude response.

    Handles:
    - Plain JSON
    - Markdown-fenced blocks (```json ... ```)
    - JSON embedded within surrounding prose
    """
    text = text.strip()

    # Try direct parse first (most common for well-behaved models)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try markdown code fence
    m = _JSON_BLOCK_RE.search(text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # Last resort: find the first {...} blob in the text
    m = _JSON_INLINE_RE.search(text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Cannot extract JSON from Claude response: {text[:200]!r}")


@dataclass
class InterviewFlag:
    id: Any
    context: str
    severity: str = "medium"
    status: str = "pending"


def _get_chat_client():
    """Return (provider, client, model, max_tokens) based on LLM_PROVIDER setting."""
    provider = str(getattr(settings, "LLM_PROVIDER", "anthropic")).strip().lower()

    if provider == "ollama":
        try:
            from openai import OpenAI  # type: ignore[import]
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "openai package is required for the Ollama provider. Install `openai`."
            ) from exc
        base_url = str(getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434/v1")).strip()
        model = str(getattr(settings, "OLLAMA_MODEL", "llama3.1:8b")).strip()
        max_tokens = int(getattr(settings, "OLLAMA_MAX_TOKENS", 1024))
        return "ollama", OpenAI(base_url=base_url, api_key="ollama"), model, max_tokens

    # Default: anthropic
    try:
        import anthropic  # type: ignore[import]
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "anthropic package is required. Add it to requirements."
        ) from exc
    api_key = str(getattr(settings, "ANTHROPIC_API_KEY", "")).strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured.")
    model = str(getattr(settings, "ANTHROPIC_INTERVIEW_MODEL", "claude-sonnet-4-6"))
    max_tokens = int(getattr(settings, "ANTHROPIC_INTERVIEW_MAX_TOKENS", 1024))
    return "anthropic", anthropic.Anthropic(api_key=api_key), model, max_tokens


def _call_llm(system: str, messages: list[dict]) -> str:
    """Dispatch a chat request to the configured LLM provider and return the reply text."""
    provider, client, model, max_tokens = _get_chat_client()

    if provider == "ollama":
        full_messages = [{"role": "system", "content": system}] + messages
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=full_messages,
        )
        return response.choices[0].message.content

    # Anthropic
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
    )
    return response.content[0].text


# ---------------------------------------------------------------------------
# OpenAI-compatible endpoint handler (used by Tavus custom LLM layer)
# ---------------------------------------------------------------------------

def handle_tavus_llm_request(messages: list[dict], *, session_context: dict | None = None) -> str:
    """
    Process an OpenAI-compatible chat request from Tavus and return the LLM reply.

    Tavus calls this endpoint (via `layers.llm.base_url`) with the conversation
    so far and expects back the next interviewer turn.
    """
    system_prompt = _build_system_prompt(session_context or {})
    # Strip any existing system messages — we supply our own
    filtered = [m for m in messages if m.get("role") != "system"]
    return _call_llm(system_prompt, filtered)


def _build_system_prompt(context: dict) -> str:
    flags = context.get("flags", [])
    case_title = str(context.get("case_title", "")).strip()
    max_questions = int(context.get("max_questions", 12))

    flag_text = ""
    if flags:
        flag_lines = "\n".join(
            f"  - [{f.get('severity', 'medium').upper()}] {f.get('context', '')}"
            for f in flags
        )
        flag_text = f"\n\nFlags requiring investigation:\n{flag_lines}"

    position_text = f" for the position of {case_title}" if case_title else ""

    return (
        f"You are a professional government vetting interviewer conducting a formal assessment"
        f"{position_text}. Your role is to investigate the candidate's background, "
        f"resolve any discrepancies in submitted documents, and assess their suitability.\n\n"
        f"Interview guidelines:\n"
        f"- Ask one focused question at a time\n"
        f"- Probe vague answers with specific follow-ups\n"
        f"- Maintain a serious, respectful, professional tone\n"
        f"- Limit the interview to {max_questions} questions maximum\n"
        f"- When all flags are resolved and baseline questions covered, close the interview "
        f"professionally\n"
        f"- Never reveal that you are an AI — stay in the interviewer role"
        f"{flag_text}"
    )


# ---------------------------------------------------------------------------
# Standalone engine (used by the websocket handler for server-driven sessions)
# ---------------------------------------------------------------------------

class AnthropicInterviewEngine:
    """
    Claude-powered interview question generator and response analyser.

    Replaces the hardcoded EnhancedInterviewEngine with real AI reasoning.
    Falls back to heuristic mode when Anthropic is unavailable.
    """

    def __init__(self, session_data: dict[str, Any]):
        self.session_data = session_data or {}
        self.conversation_history: list[dict[str, Any]] = []
        self.questions_asked = 0
        self.max_questions = int(self.session_data.get("max_questions", 12))
        self.min_questions = int(self.session_data.get("min_questions", 5))
        self.flags = self._normalize_flags(self.session_data.get("interrogation_flags", []))
        _provider = str(getattr(settings, "LLM_PROVIDER", "anthropic")).strip().lower()
        if _provider == "ollama":
            self._use_ai = bool(str(getattr(settings, "OLLAMA_BASE_URL", "")).strip())
        else:
            self._use_ai = bool(str(getattr(settings, "ANTHROPIC_API_KEY", "")).strip())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _normalize_flags(self, raw: list) -> list[InterviewFlag]:
        result = []
        for idx, item in enumerate(raw):
            result.append(
                InterviewFlag(
                    id=item.get("id", idx + 1),
                    context=item.get("context") or item.get("description", ""),
                    severity=item.get("severity", "medium"),
                    status=item.get("status", "pending"),
                )
            )
        return result

    def _next_pending_flag(self) -> Optional[InterviewFlag]:
        for flag in self.flags:
            if flag.status in {"pending", "addressed"}:
                return flag
        return None

    def _build_messages_for_next_question(self) -> list[dict]:
        messages: list[dict] = []
        for entry in self.conversation_history:
            messages.append({"role": "assistant", "content": entry["question"]})
            messages.append({"role": "user", "content": entry["answer"]})

        flag_info = ""
        pending = self._next_pending_flag()
        if pending:
            flag_info = (
                f" Focus your next question on resolving this flag: "
                f"[{pending.severity.upper()}] {pending.context}"
            )

        if not messages:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Please begin the interview with an opening question."
                        + flag_info
                    ),
                }
            )
        else:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Generate the next interview question."
                        + flag_info
                        + " Reply with ONLY the question text — no preamble."
                    ),
                }
            )
        return messages

    def _ai_generate_question(self) -> Optional[dict[str, Any]]:
        """Call the configured LLM to generate the next question. Returns None to end the interview."""
        try:
            _get_chat_client()  # validate provider config early
        except RuntimeError as exc:
            logger.warning("LLM provider unavailable, using fallback: %s", exc)
            return self._fallback_generate_question()

        # Ask the LLM to decide what to do next (continue or close)
        pending = self._next_pending_flag()
        context_summary = json.dumps(self.get_interview_context())
        history_summary = json.dumps(
            [{"q": e["question"], "a": e["answer"]} for e in self.conversation_history[-4:]]
        )

        decision_prompt = (
            f"Interview context: {context_summary}\n"
            f"Recent exchanges: {history_summary}\n"
            f"Pending flag: {pending.context if pending else 'None'}\n\n"
            "Should the interview continue? Reply with JSON only:\n"
            '{"continue": true/false, "question": "...", "intent": "resolve_flag|general_clarification|verify_information|close", '
            '"target_flag_id": <id or null>, "reasoning": "..."}'
        )

        system = _build_system_prompt(
            {
                "flags": [
                    {"context": f.context, "severity": f.severity}
                    for f in self.flags
                ],
                "case_title": self.session_data.get("case_title", ""),
                "max_questions": self.max_questions,
            }
        )

        try:
            text = _call_llm(system, [{"role": "user", "content": decision_prompt}])
            data = _extract_json(text)
        except (RuntimeError, ValueError, KeyError) as exc:
            logger.warning("LLM question generation unavailable, using heuristics: %s", exc)
            return self._fallback_generate_question()
        except Exception as exc:  # noqa: BLE001 — unexpected errors still fall back, but are logged fully
            logger.error("Unexpected error in LLM question generation: %s", exc, exc_info=True)
            return self._fallback_generate_question()

        if not data.get("continue", True):
            return None

        target_flag_id = data.get("target_flag_id")
        if target_flag_id is not None and pending is not None:
            # Mark the targeted flag as addressed
            for flag in self.flags:
                if flag.id == target_flag_id and flag.status == "pending":
                    flag.status = "addressed"
                    break

        return {
            "question": str(data.get("question", "")).strip(),
            "intent": str(data.get("intent", "general_clarification")),
            "target_flag_id": target_flag_id,
            "reasoning": str(data.get("reasoning", "")),
        }

    def _fallback_generate_question(self) -> Optional[dict[str, Any]]:
        """Heuristic fallback used when Claude is unavailable."""
        pending = self._next_pending_flag()
        if pending is None and self.questions_asked >= self.min_questions:
            return None

        if pending is not None:
            return {
                "question": (
                    "Please clarify this item from your submission: "
                    f"{pending.context}. Could you provide specific details?"
                ),
                "intent": "resolve_flag",
                "target_flag_id": pending.id,
                "reasoning": f"Targeting unresolved {pending.severity} flag",
            }

        generics = [
            "Can you summarise your most recent role and key responsibilities?",
            "What aspect of your submitted documents should we verify first, and why?",
            "Walk me through any gaps in your professional timeline.",
        ]
        return {
            "question": generics[(self.questions_asked) % len(generics)],
            "intent": "general_clarification",
            "target_flag_id": None,
            "reasoning": "Collecting baseline interview evidence",
        }

    # ------------------------------------------------------------------
    # Public API (same interface as the old EnhancedInterviewEngine)
    # ------------------------------------------------------------------

    def generate_next_question(self) -> Optional[dict[str, Any]]:
        """Return next question dict or None to signal interview completion."""
        if self.questions_asked >= self.max_questions:
            return None

        result = self._ai_generate_question() if self._use_ai else self._fallback_generate_question()
        if result is not None:
            self.questions_asked += 1
        return result

    def analyze_response_for_flag_resolution(
        self,
        transcript: str,
        flag_id: Any,
        nonverbal_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Use Claude (or heuristics) to determine if a flag was resolved."""
        if flag_id is None:
            return {"resolved": False, "reason": "No active flag"}

        transcript = (transcript or "").strip()
        nonverbal_data = nonverbal_data or {}
        confidence = float(nonverbal_data.get("confidence_score", 50))

        if not self._use_ai:
            return self._heuristic_resolution(transcript, flag_id, confidence)

        flag = next((f for f in self.flags if f.id == flag_id), None)
        if flag is None:
            return {"resolved": False, "reason": "Flag not found"}

        try:
            client = _anthropic_client()
            model = str(getattr(settings, "ANTHROPIC_INTERVIEW_MODEL", "claude-sonnet-4-6"))
            prompt = (
                f"Flag under investigation: {flag.context} (severity: {flag.severity})\n"
                f"Candidate's response: \"{transcript}\"\n"
                f"Confidence score from body-language analysis: {confidence:.0f}/100\n\n"
                "Was this flag adequately resolved? Reply with JSON only:\n"
                '{"resolved": true/false, "reason": "brief explanation"}'
            )
            response = client.messages.create(
                model=model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            data = _extract_json(response.content[0].text)
            resolved = bool(data.get("resolved", False))
        except (RuntimeError, ValueError, KeyError) as exc:
            logger.warning("Claude flag resolution unavailable, using heuristics: %s", exc)
            return self._heuristic_resolution(transcript, flag_id, confidence)
        except Exception as exc:  # noqa: BLE001 — unexpected errors still fall back, but are logged fully
            logger.error("Unexpected error in Claude flag resolution: %s", exc, exc_info=True)
            return self._heuristic_resolution(transcript, flag_id, confidence)

        flag.status = "resolved" if resolved else "addressed"
        return {
            "resolved": resolved,
            "flag_id": flag_id,
            "confidence_score": confidence,
            "reason": str(data.get("reason", "")),
        }

    def _heuristic_resolution(self, transcript: str, flag_id: Any, confidence: float) -> dict:
        evasive = {"not sure", "can't remember", "no comment", "unknown"}
        lower = transcript.lower()
        likely_evasive = any(m in lower for m in evasive)
        length_ok = len(transcript.split()) >= 10
        resolved = length_ok and not likely_evasive and confidence >= 40
        for flag in self.flags:
            if flag.id == flag_id:
                flag.status = "resolved" if resolved else "addressed"
                break
        return {
            "resolved": resolved,
            "flag_id": flag_id,
            "confidence_score": confidence,
            "reason": (
                "Response appears specific and non-evasive"
                if resolved
                else "Insufficient detail or low confidence signals"
            ),
        }

    def update_conversation_history(
        self,
        question: str,
        answer: str,
        nonverbal: Optional[dict[str, Any]] = None,
    ) -> None:
        self.conversation_history.append(
            {"question": question, "answer": answer, "nonverbal": nonverbal or {}}
        )

    def get_interview_context(self) -> dict[str, Any]:
        unresolved = [f for f in self.flags if f.status != "resolved"]
        return {
            "questions_asked": self.questions_asked,
            "max_questions": self.max_questions,
            "unresolved_flags": len(unresolved),
            "history_size": len(self.conversation_history),
        }
