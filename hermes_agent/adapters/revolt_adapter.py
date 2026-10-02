"""Revolt adapter — wraps the `revolt.py` library behind the ChatAdapter interface.

CAVEAT: revolt.py's API has shifted across versions, and this was written without
live access to that library's current documentation. The shape here (an
aiohttp.ClientSession passed into revolt.Client, overriding on_ready/on_message,
`self.user.mentioned_in(message)`) matches that library's typical discord.py-like
design, but verify it against whatever version actually gets installed
(`pip show revolt.py`) before relying on this in production — adjust method/
attribute names here if they've changed. This adapter is inactive unless
REVOLT_TOKEN is set in .env, so it has zero effect on the Discord-only path.
"""

from __future__ import annotations

import aiohttp
import revolt

from .. import metrics
from .base import ChatAdapter, IncomingMessage


class RevoltAdapter(ChatAdapter):
    name = "revolt"

    def __init__(
        self,
        token: str,
        command_prefix: str,
        mention_trigger: bool,
        allowed_channel_ids: set[str],
    ) -> None:
        super().__init__()
        self._token = token
        self._command_prefix = command_prefix
        self._mention_trigger = mention_trigger
        self._allowed_channel_ids = allowed_channel_ids
        self._session: aiohttp.ClientSession | None = None
        self._client: _InnerClient | None = None

    async def start(self) -> None:
        self._session = aiohttp.ClientSession()
        self._client = _InnerClient(
            adapter=self,
            session=self._session,
            token=self._token,
            command_prefix=self._command_prefix,
            mention_trigger=self._mention_trigger,
            allowed_channel_ids=self._allowed_channel_ids,
        )
        await self._client.start()

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
        if self._session is not None:
            await self._session.close()


class _InnerClient(revolt.Client):
    def __init__(
        self,
        adapter: RevoltAdapter,
        session: aiohttp.ClientSession,
        token: str,
        command_prefix: str,
        mention_trigger: bool,
        allowed_channel_ids: set[str],
    ) -> None:
        super().__init__(session, token)
        self._adapter = adapter
        self._command_prefix = command_prefix
        self._mention_trigger = mention_trigger
        self._allowed_channel_ids = allowed_channel_ids

    async def on_ready(self) -> None:
        metrics.log_event("startup", message=f"revolt logged in as {self.user}")

    def _extract_text(self, message: revolt.Message) -> str | None:
        content = message.content
        if content.startswith(self._command_prefix):
            return content[len(self._command_prefix) :].strip()
        if self._mention_trigger and self.user.mentioned_in(message):
            return content.replace(f"<@{self.user.id}>", "").strip()
        return None

    async def on_message(self, message: revolt.Message) -> None:
        if message.author.bot:
            return
        if (
            self._allowed_channel_ids
            and str(message.channel.id) not in self._allowed_channel_ids
        ):
            return

        text = self._extract_text(message)
        if text is None or self._adapter.on_message is None:
            return

        async def reply(text_out: str) -> None:
            await message.channel.send(text_out)

        guild_id = None
        server = getattr(message.channel, "server", None)
        if server is not None:
            guild_id = str(server.id)

        incoming = IncomingMessage(
            platform="revolt",
            channel_id=str(message.channel.id),
            guild_id=guild_id,
            content=text,
            reply=reply,
            # revolt.py has no typing-indicator API used here; defaults to the
            # no-op from IncomingMessage.
        )
        await self._adapter.on_message(incoming)
