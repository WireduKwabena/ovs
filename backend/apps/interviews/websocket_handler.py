import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer

from ai_ml_services.interview.websocket_handler import (
    handle_websocket_message,
    initialize_interview_session,
    manager,
)

logger = logging.getLogger(__name__)


class InterviewConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session_id = str(self.scope["url_route"]["kwargs"]["session_id"])
        self._chunk_index = 0

        await manager.connect(self.session_id, self)
        initialized = await initialize_interview_session(self.session_id, self)
        if not initialized:
            await self.close(code=4400)

    async def receive(self, text_data=None, bytes_data=None):
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
            await self.send_json({"type": "error", "message": "Invalid JSON payload."})
        except Exception as exc:
            logger.error("Interview websocket error for session %s: %s", self.session_id, exc, exc_info=True)
            await self.send_json({"type": "error", "message": "Failed to process websocket message."})

    async def disconnect(self, close_code):
        manager.disconnect(self.session_id)
