"""Local web chat adapter — talks to CommandRouter exactly like Discord does, over a
WebSocket instead of the Discord gateway. No Discord account, invite, or token
required; this is the "chat with Hermes without Discord" path.

Runs an embedded FastAPI/uvicorn server inside the same process as the Discord
adapter (see main.py's asyncio.gather), on its own published port — see
docker-compose.yml and docs/INSTALL.md for the matching firewalld rule (same
LOCAL_SUBNET-only, no-NAT-forward posture as Grafana and the task dashboard). No
auth of its own, same accepted tradeoff as those two.
"""

from __future__ import annotations

import os
import uuid

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from .base import ChatAdapter, IncomingMessage

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "web_static")


class WebAdapter(ChatAdapter):
    name = "web"

    def __init__(self, port: int) -> None:
        super().__init__()
        self._port = port
        self._app = FastAPI(title="Hermes Web Chat")
        self._app.get("/")(self._index)
        self._app.websocket("/ws")(self._websocket_endpoint)
        self._server: uvicorn.Server | None = None

    async def _index(self) -> FileResponse:
        return FileResponse(os.path.join(_STATIC_DIR, "index.html"))

    async def _websocket_endpoint(self, websocket: WebSocket) -> None:
        await websocket.accept()
        session_id = uuid.uuid4().hex

        async def reply(text_out: str) -> None:
            await websocket.send_text(text_out)

        try:
            while True:
                text = (await websocket.receive_text()).strip()
                if not text or self.on_message is None:
                    continue
                incoming = IncomingMessage(
                    platform="web",
                    channel_id=session_id,
                    guild_id=None,
                    content=text,
                    reply=reply,
                )
                await self.on_message(incoming)
        except WebSocketDisconnect:
            pass

    async def start(self) -> None:
        config = uvicorn.Config(self._app, host="0.0.0.0", port=self._port, log_level="warning")
        self._server = uvicorn.Server(config)
        await self._server.serve()

    async def close(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
