import json
import logging
import time
from urllib.parse import parse_qs, unquote_plus

from django.conf import settings
from channels.generic.websocket import AsyncWebsocketConsumer

from ai_ml_services.interview.websocket_handler import (
    handle_websocket_message,
    initialize_interview_session,
    manager,
)

logger = logging.getLogger(__name__)

# Maximum WebSocket messages per minute per session (distributed via Redis).
# Configurable via WS_INTERVIEW_RATE_LIMIT_PER_MINUTE in settings.
_WS_RATE_LIMIT_PER_MINUTE: int = getattr(settings, "WS_INTERVIEW_RATE_LIMIT_PER_MINUTE", 120)

try:
    import redis.asyncio as _aioredis  # type: ignore[import]
    _REDIS_AVAILABLE = True
except ImportError:
    _aioredis = None  # type: ignore[assignment]
    _REDIS_AVAILABLE = False


class InterviewConsumer(AsyncWebsocketConsumer):
    def _validate_ws_token(self) -> bool:
        """
        Validate the JWT access token passed as ?token=<access_token> in the
        WebSocket URL.  Only signature and expiry are checked (no DB blacklist
        lookup) — sufficient for a short-lived (1 h) access token.
        """
        try:
            from rest_framework_simplejwt.tokens import UntypedToken
            from rest_framework_simplejwt.exceptions import TokenError

            query_string = self.scope.get("query_string", b"").decode("utf-8", errors="replace")
            params = parse_qs(query_string)
            token_list = params.get("token", [])
            if not token_list:
                logger.warning(
                    "WebSocket connection rejected: missing token for session %s",
                    self.session_id,
                )
                return False
            UntypedToken(unquote_plus(token_list[0]))
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "WebSocket auth failed for session %s: %s",
                self.session_id,
                exc,
            )
            return False

    async def connect(self):
        self.session_id = str(self.scope["url_route"]["kwargs"]["session_id"])
        self._chunk_index = 0
        # Fallback per-connection sliding-window used when Redis is unavailable.
        self._message_timestamps: list[float] = []
        # Redis connection for distributed rate limiting across load-balanced nodes.
        self._redis = None

        # Reject unauthenticated connections before doing any real work.
        if not self._validate_ws_token():
            await self.accept()
            await self.close(code=4401)
            return

        if _REDIS_AVAILABLE:
            try:
                redis_url: str = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
                self._redis = _aioredis.from_url(redis_url, decode_responses=True)
            except Exception as exc:  # noqa: BLE001
                logger.warning("WebSocket Redis connection failed; using per-connection rate limit: %s", exc)

        await manager.connect(self.session_id, self)
        initialized = await initialize_interview_session(self.session_id, self)
        if not initialized:
            await self.close(code=4400)

    async def _is_rate_limited(self) -> bool:
        """
        Distributed sliding-window rate limit backed by Redis INCR+EXPIRE.
        Falls back to per-connection tracking when Redis is unavailable.
        Returns True if the per-minute limit for this session has been exceeded.
        """
        if self._redis is not None:
            try:
                # Composite key: session + channel prevents a client who knows a session ID
                # from exhausting the limit on behalf of a different connection.
                channel = getattr(self, "channel_name", "unknown")
                key = f"ws:ratelimit:{self.session_id}:{channel}"
                count = await self._redis.incr(key)
                if count == 1:
                    await self._redis.expire(key, 60)
                return count > _WS_RATE_LIMIT_PER_MINUTE
            except Exception as exc:  # noqa: BLE001
                logger.warning("Redis rate-limit check failed for session %s; using fallback: %s", self.session_id, exc)

        # Fallback: in-memory sliding window (single-node only).
        now = time.monotonic()
        cutoff = now - 60.0
        self._message_timestamps = [t for t in self._message_timestamps if t > cutoff]
        self._message_timestamps.append(now)
        return len(self._message_timestamps) > _WS_RATE_LIMIT_PER_MINUTE

    async def receive(self, text_data=None, bytes_data=None):
        if await self._is_rate_limited():
            logger.warning(
                "WebSocket rate limit exceeded for session %s. Dropping message.",
                self.session_id,
            )
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": "Rate limit exceeded. Slow down your requests.",
            }))
            return

        try:
            if text_data:
                payload = json.loads(text_data)
                await handle_websocket_message(payload, self.session_id, self)
                return

            if bytes_data is not None:
                self._chunk_index += 1
                await handle_websocket_message(
                    {
                        "type": "video_chunk",
                        "index": self._chunk_index,
                        "chunk_size": len(bytes_data),
                    },
                    self.session_id,
                    self,
                )
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({"type": "error", "message": "Invalid JSON payload."}))
        except Exception as exc:
            logger.error("Interview websocket error for session %s: %s", self.session_id, exc, exc_info=True)
            await self.send(text_data=json.dumps({"type": "error", "message": "Failed to process websocket message."}))

    async def disconnect(self, close_code):
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:  # noqa: BLE001
                pass
        manager.disconnect(self.session_id)
