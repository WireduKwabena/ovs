"""Tests for LLM provider switching in the interview engine.

Three test tiers:
  1. Unit tests  — fully mocked; always run in CI (no external services needed).
  2. Integration — skipped unless a live Ollama server is reachable at OLLAMA_BASE_URL.

To run only unit tests:
    python manage.py test ai_ml_services.tests.test_interview_engine_providers.EngineUnitTests

To run integration tests (requires `ollama run llama3.1:8b` running locally):
    python manage.py test ai_ml_services.tests.test_interview_engine_providers.OllamaIntegrationTests
"""

from __future__ import annotations

import json
import os
import urllib.request
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_anthropic_response(text: str):
    """Minimal stub for anthropic.messages.create() return value."""
    content_block = SimpleNamespace(text=text)
    return SimpleNamespace(content=[content_block])


def _make_openai_response(text: str):
    """Minimal stub for openai.chat.completions.create() return value."""
    message = SimpleNamespace(content=text)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


_CONTINUE_JSON = json.dumps({
    "continue": True,
    "question": "Can you describe your role at your previous organisation?",
    "intent": "general_clarification",
    "target_flag_id": None,
    "reasoning": "Opening question to establish background.",
})

_CLOSE_JSON = json.dumps({
    "continue": False,
    "question": "",
    "intent": "close",
    "target_flag_id": None,
    "reasoning": "All topics covered.",
})


# ---------------------------------------------------------------------------
# Unit tests — fully mocked, no live service required
# ---------------------------------------------------------------------------

class EngineUnitTests(SimpleTestCase):
    """Provider-routing logic tested with mocked LLM clients."""

    # ------------------------------------------------------------------
    # _get_chat_client / _call_llm routing
    # ------------------------------------------------------------------

    @override_settings(
        LLM_PROVIDER="anthropic",
        ANTHROPIC_API_KEY="sk-ant-test",
        ANTHROPIC_INTERVIEW_MODEL="claude-test",
        ANTHROPIC_INTERVIEW_MAX_TOKENS=512,
    )
    def test_get_chat_client_returns_anthropic(self):
        mock_anthropic_mod = MagicMock()
        mock_client = MagicMock()
        mock_anthropic_mod.Anthropic.return_value = mock_client

        with patch.dict("sys.modules", {"anthropic": mock_anthropic_mod}):
            from ai_ml_services.interview.anthropic_interview_engine import _get_chat_client
            provider, client, model, max_tokens = _get_chat_client()

        self.assertEqual(provider, "anthropic")
        self.assertEqual(model, "claude-test")
        self.assertEqual(max_tokens, 512)
        mock_anthropic_mod.Anthropic.assert_called_once_with(api_key="sk-ant-test")

    @override_settings(
        LLM_PROVIDER="ollama",
        OLLAMA_BASE_URL="http://localhost:11434/v1",
        OLLAMA_MODEL="llama3.1:8b",
        OLLAMA_MAX_TOKENS=768,
    )
    def test_get_chat_client_returns_ollama(self):
        mock_openai_mod = MagicMock()
        mock_client_instance = MagicMock()
        mock_openai_mod.OpenAI.return_value = mock_client_instance

        with patch.dict("sys.modules", {"openai": mock_openai_mod}):
            from ai_ml_services.interview.anthropic_interview_engine import _get_chat_client
            provider, client, model, max_tokens = _get_chat_client()

        self.assertEqual(provider, "ollama")
        self.assertEqual(model, "llama3.1:8b")
        self.assertEqual(max_tokens, 768)
        mock_openai_mod.OpenAI.assert_called_once_with(
            base_url="http://localhost:11434/v1", api_key="ollama"
        )

    @override_settings(LLM_PROVIDER="anthropic", ANTHROPIC_API_KEY="")
    def test_get_chat_client_raises_when_anthropic_key_missing(self):
        from ai_ml_services.interview.anthropic_interview_engine import _get_chat_client
        with self.assertRaises(RuntimeError, msg="ANTHROPIC_API_KEY is not configured"):
            _get_chat_client()

    # ------------------------------------------------------------------
    # _call_llm dispatches to correct client method
    # ------------------------------------------------------------------

    @override_settings(
        LLM_PROVIDER="anthropic",
        ANTHROPIC_API_KEY="sk-ant-test",
        ANTHROPIC_INTERVIEW_MODEL="claude-test",
        ANTHROPIC_INTERVIEW_MAX_TOKENS=512,
    )
    def test_call_llm_uses_anthropic_messages_create(self):
        from ai_ml_services.interview import anthropic_interview_engine as mod

        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_anthropic_response("Hello from Claude")

        with patch.object(mod, "_get_chat_client", return_value=("anthropic", mock_client, "claude-test", 512)):
            result = mod._call_llm("system prompt", [{"role": "user", "content": "hi"}])

        self.assertEqual(result, "Hello from Claude")
        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args[1]
        self.assertEqual(call_kwargs["system"], "system prompt")

    @override_settings(
        LLM_PROVIDER="ollama",
        OLLAMA_BASE_URL="http://localhost:11434/v1",
        OLLAMA_MODEL="llama3.1:8b",
        OLLAMA_MAX_TOKENS=512,
    )
    def test_call_llm_uses_openai_chat_completions_for_ollama(self):
        from ai_ml_services.interview import anthropic_interview_engine as mod

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_openai_response("Hello from Ollama")

        with patch.object(mod, "_get_chat_client", return_value=("ollama", mock_client, "llama3.1:8b", 512)):
            result = mod._call_llm("system prompt", [{"role": "user", "content": "hi"}])

        self.assertEqual(result, "Hello from Ollama")
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        # System message must be prepended for Ollama
        self.assertEqual(call_kwargs["messages"][0]["role"], "system")
        self.assertEqual(call_kwargs["messages"][0]["content"], "system prompt")

    # ------------------------------------------------------------------
    # handle_tavus_llm_request
    # ------------------------------------------------------------------

    def test_handle_tavus_llm_request_strips_system_messages_and_calls_llm(self):
        from ai_ml_services.interview import anthropic_interview_engine as mod

        incoming = [
            {"role": "system", "content": "old system"},
            {"role": "user", "content": "question"},
            {"role": "assistant", "content": "answer"},
        ]

        with patch.object(mod, "_call_llm", return_value="Next question text") as mock_call:
            result = mod.handle_tavus_llm_request(incoming, session_context={"case_title": "Director"})

        self.assertEqual(result, "Next question text")
        _, passed_messages = mock_call.call_args[0]
        # System message must have been stripped
        roles = [m["role"] for m in passed_messages]
        self.assertNotIn("system", roles)

    # ------------------------------------------------------------------
    # AnthropicInterviewEngine._use_ai flag
    # ------------------------------------------------------------------

    @override_settings(LLM_PROVIDER="anthropic", ANTHROPIC_API_KEY="sk-ant-test")
    def test_use_ai_true_when_anthropic_key_present(self):
        from ai_ml_services.interview.anthropic_interview_engine import AnthropicInterviewEngine
        engine = AnthropicInterviewEngine({"max_questions": 5})
        self.assertTrue(engine._use_ai)

    @override_settings(LLM_PROVIDER="anthropic", ANTHROPIC_API_KEY="")
    def test_use_ai_false_when_anthropic_key_absent(self):
        from ai_ml_services.interview.anthropic_interview_engine import AnthropicInterviewEngine
        engine = AnthropicInterviewEngine({"max_questions": 5})
        self.assertFalse(engine._use_ai)

    @override_settings(LLM_PROVIDER="ollama", OLLAMA_BASE_URL="http://localhost:11434/v1")
    def test_use_ai_true_when_ollama_base_url_present(self):
        from ai_ml_services.interview.anthropic_interview_engine import AnthropicInterviewEngine
        engine = AnthropicInterviewEngine({"max_questions": 5})
        self.assertTrue(engine._use_ai)

    @override_settings(LLM_PROVIDER="ollama", OLLAMA_BASE_URL="")
    def test_use_ai_false_when_ollama_base_url_absent(self):
        from ai_ml_services.interview.anthropic_interview_engine import AnthropicInterviewEngine
        engine = AnthropicInterviewEngine({"max_questions": 5})
        self.assertFalse(engine._use_ai)

    # ------------------------------------------------------------------
    # _ai_generate_question fallback on provider error
    # ------------------------------------------------------------------

    @override_settings(LLM_PROVIDER="anthropic", ANTHROPIC_API_KEY="sk-ant-test")
    def test_ai_generate_question_falls_back_on_runtime_error(self):
        from ai_ml_services.interview import anthropic_interview_engine as mod

        engine = mod.AnthropicInterviewEngine(
            {"max_questions": 5, "min_questions": 1, "case_title": "Test"}
        )
        engine._use_ai = True

        with patch.object(mod, "_get_chat_client", side_effect=RuntimeError("no key")):
            result = engine._ai_generate_question()

        # Should return a heuristic question dict, not raise
        self.assertIsInstance(result, dict)
        self.assertIn("question", result)

    @override_settings(LLM_PROVIDER="anthropic", ANTHROPIC_API_KEY="sk-ant-test",
                       ANTHROPIC_INTERVIEW_MODEL="claude-test", ANTHROPIC_INTERVIEW_MAX_TOKENS=512)
    def test_ai_generate_question_returns_question_on_success(self):
        from ai_ml_services.interview import anthropic_interview_engine as mod

        engine = mod.AnthropicInterviewEngine(
            {"max_questions": 5, "min_questions": 1, "case_title": "Director"}
        )

        with patch.object(mod, "_get_chat_client", return_value=("anthropic", MagicMock(), "claude-test", 512)):
            with patch.object(mod, "_call_llm", return_value=_CONTINUE_JSON):
                result = engine._ai_generate_question()

        self.assertIsNotNone(result)
        self.assertEqual(result["question"], "Can you describe your role at your previous organisation?")
        self.assertEqual(result["intent"], "general_clarification")

    @override_settings(LLM_PROVIDER="anthropic", ANTHROPIC_API_KEY="sk-ant-test",
                       ANTHROPIC_INTERVIEW_MODEL="claude-test", ANTHROPIC_INTERVIEW_MAX_TOKENS=512)
    def test_ai_generate_question_returns_none_when_llm_says_close(self):
        from ai_ml_services.interview import anthropic_interview_engine as mod

        engine = mod.AnthropicInterviewEngine(
            {"max_questions": 5, "min_questions": 1, "case_title": "Director"}
        )
        engine.questions_asked = 5

        with patch.object(mod, "_get_chat_client", return_value=("anthropic", MagicMock(), "claude-test", 512)):
            with patch.object(mod, "_call_llm", return_value=_CLOSE_JSON):
                result = engine._ai_generate_question()

        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Integration tests — skipped unless Ollama is reachable
# ---------------------------------------------------------------------------

def _ollama_reachable() -> bool:
    """Return True if the Ollama API server is responding at OLLAMA_BASE_URL."""
    raw = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    # Derive the health-check URL from the base URL
    health_url = raw.rstrip("/v1").rstrip("/") + "/api/tags"
    try:
        with urllib.request.urlopen(health_url, timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


import unittest

_SKIP_REASON = (
    "Ollama server not reachable — start `ollama run llama3.1:8b` "
    "and set LLM_PROVIDER=ollama in your .env to run these tests."
)


@unittest.skipUnless(_ollama_reachable(), _SKIP_REASON)
class OllamaIntegrationTests(SimpleTestCase):
    """Live integration tests — require a running Ollama instance.

    These tests exercise the full path from _get_chat_client() through to
    a real model response. They run only when Ollama is reachable, so they
    are safe to leave in the suite without breaking CI.
    """

    OLLAMA_SETTINGS = dict(
        LLM_PROVIDER="ollama",
        OLLAMA_BASE_URL=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        OLLAMA_MODEL=os.environ.get("OLLAMA_MODEL", "llama3.1:8b"),
        OLLAMA_MAX_TOKENS=256,
    )

    @override_settings(**OLLAMA_SETTINGS)
    def test_call_llm_returns_nonempty_string(self):
        from ai_ml_services.interview.anthropic_interview_engine import _call_llm

        result = _call_llm(
            "You are a terse assistant. Reply with one sentence only.",
            [{"role": "user", "content": "Say hello."}],
        )
        self.assertIsInstance(result, str)
        self.assertGreater(len(result.strip()), 0)

    @override_settings(**OLLAMA_SETTINGS)
    def test_engine_generates_interview_question(self):
        from ai_ml_services.interview.anthropic_interview_engine import AnthropicInterviewEngine

        engine = AnthropicInterviewEngine({
            "case_title": "Deputy Director, Ministry of Finance",
            "max_questions": 3,
            "min_questions": 1,
            "interrogation_flags": [],
        })
        self.assertTrue(engine._use_ai, "Expected _use_ai=True with OLLAMA_BASE_URL set")

        result = engine._ai_generate_question()
        # Result is a question dict or None (if model decided to close immediately)
        self.assertTrue(result is None or isinstance(result, dict))
        if result is not None:
            self.assertIn("question", result)
            self.assertGreater(len(result["question"].strip()), 0)

    @override_settings(**OLLAMA_SETTINGS)
    def test_handle_tavus_llm_request_returns_reply(self):
        from ai_ml_services.interview.anthropic_interview_engine import handle_tavus_llm_request

        messages = [{"role": "user", "content": "Hello, please begin the interview."}]
        reply = handle_tavus_llm_request(messages, session_context={"case_title": "Auditor General"})

        self.assertIsInstance(reply, str)
        self.assertGreater(len(reply.strip()), 0)
