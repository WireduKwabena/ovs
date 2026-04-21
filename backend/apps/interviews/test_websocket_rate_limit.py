"""Tests for WebSocket per-connection rate limiting in InterviewConsumer."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

from django.test import SimpleTestCase, override_settings

from apps.interviews.websocket_handler import InterviewConsumer, _WS_RATE_LIMIT_PER_MINUTE


class WebSocketRateLimitConfigTests(SimpleTestCase):
    def test_default_rate_limit_is_120(self):
        self.assertEqual(_WS_RATE_LIMIT_PER_MINUTE, 120)

    @override_settings(WS_INTERVIEW_RATE_LIMIT_PER_MINUTE=60)
    def test_rate_limit_is_configurable(self):
        # Re-import to pick up new setting
        import importlib
        import apps.interviews.websocket_handler as ws_module
        importlib.reload(ws_module)
        self.assertEqual(ws_module._WS_RATE_LIMIT_PER_MINUTE, 60)
        # Restore
        importlib.reload(ws_module)


class InterviewConsumerRateLimitTests(SimpleTestCase):
    """Unit tests for _is_rate_limited per-connection logic."""

    def _make_consumer(self):
        consumer = InterviewConsumer.__new__(InterviewConsumer)
        consumer._message_timestamps = []
        consumer.session_id = "test-session-123"
        consumer._redis = None  # force in-memory fallback
        return consumer

    def _call(self, consumer):
        return asyncio.get_event_loop().run_until_complete(consumer._is_rate_limited())

    def test_first_message_is_not_rate_limited(self):
        consumer = self._make_consumer()
        self.assertFalse(self._call(consumer))

    def test_messages_within_limit_are_not_rate_limited(self):
        consumer = self._make_consumer()
        with patch("apps.interviews.websocket_handler._WS_RATE_LIMIT_PER_MINUTE", 5):
            for _ in range(5):
                result = self._call(consumer)
            self.assertFalse(result)

    def test_message_exceeding_limit_is_rate_limited(self):
        consumer = self._make_consumer()
        with patch("apps.interviews.websocket_handler._WS_RATE_LIMIT_PER_MINUTE", 3):
            for _ in range(3):
                self._call(consumer)
            # 4th call exceeds limit of 3
            self.assertTrue(self._call(consumer))

    def test_old_timestamps_are_pruned(self):
        consumer = self._make_consumer()
        # Inject timestamps older than 60 seconds
        old_time = time.monotonic() - 61.0
        consumer._message_timestamps = [old_time] * 100

        with patch("apps.interviews.websocket_handler._WS_RATE_LIMIT_PER_MINUTE", 5):
            # Old timestamps should be pruned, so this should NOT be rate limited
            result = self._call(consumer)
        self.assertFalse(result)
        # Old entries removed, only the new one remains
        self.assertEqual(len(consumer._message_timestamps), 1)

    def test_rate_limit_is_per_connection_not_global(self):
        """Two separate consumers each have their own timestamp list."""
        consumer1 = self._make_consumer()
        consumer2 = self._make_consumer()

        with patch("apps.interviews.websocket_handler._WS_RATE_LIMIT_PER_MINUTE", 2):
            # Exhaust consumer1's limit
            for _ in range(3):
                self._call(consumer1)
            # consumer2 should still be unaffected
            self.assertFalse(self._call(consumer2))
            # consumer1 should be limited
            self.assertTrue(self._call(consumer1))


class InterviewConsumerReceiveRateLimitTests(SimpleTestCase):
    """Async tests: receive() must drop messages and send error when limited."""

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def _make_consumer(self):
        consumer = InterviewConsumer.__new__(InterviewConsumer)
        consumer._message_timestamps = []
        consumer.session_id = "test-session-456"
        consumer._chunk_index = 0
        consumer._authenticated = True  # skip auth gate so tests reach rate-limit logic
        consumer._redis = None
        consumer.send = AsyncMock()
        consumer.close = AsyncMock()
        return consumer

    def test_receive_drops_message_when_rate_limited(self):
        consumer = self._make_consumer()

        # Force rate limit to trigger
        consumer._is_rate_limited = AsyncMock(return_value=True)

        async def run():
            await consumer.receive(text_data='{"type": "ping"}')

        with patch("apps.interviews.websocket_handler.handle_websocket_message", new_callable=AsyncMock) as mock_handler:
            self._run(run())
            mock_handler.assert_not_called()

        consumer.send.assert_called_once()
        sent_arg = consumer.send.call_args[1]["text_data"]
        import json
        payload = json.loads(sent_arg)
        self.assertEqual(payload["type"], "error")
        self.assertIn("Rate limit", payload["message"])

    def test_receive_processes_message_when_not_rate_limited(self):
        consumer = self._make_consumer()
        consumer._is_rate_limited = AsyncMock(return_value=False)

        async def run():
            await consumer.receive(text_data='{"type": "ping"}')

        with patch(
            "apps.interviews.websocket_handler.handle_websocket_message",
            new_callable=AsyncMock,
        ) as mock_handler:
            self._run(run())
            mock_handler.assert_called_once()

    def test_receive_returns_error_on_invalid_json(self):
        consumer = self._make_consumer()
        consumer._is_rate_limited = AsyncMock(return_value=False)

        async def run():
            await consumer.receive(text_data="not json {{{{")

        with patch("apps.interviews.websocket_handler.handle_websocket_message", new_callable=AsyncMock):
            self._run(run())

        consumer.send.assert_called_once()
        import json
        payload = json.loads(consumer.send.call_args[1]["text_data"])
        self.assertEqual(payload["type"], "error")
        self.assertIn("Invalid JSON", payload["message"])
