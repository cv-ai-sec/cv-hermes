"""Discord adapter — wraps discord.py behind the ChatAdapter interface."""

from __future__ import annotations

import discord

from .. import metrics
from .base import ChatAdapter, IncomingMessage

MAX_DISCORD_MESSAGE = 2000


class DiscordAdapter(ChatAdapter):
    name = "discord"

    def __init__(
        self,
        token: str,
        command_prefix: str,
        mention_trigger: bool,
        allowed_guild_ids: set[int],
    ) -> None:
        super().__init__()
        self._token = token

        intents = discord.Intents.default()
        intents.message_content = True
        self._client = _InnerClient(
            adapter=self,
            command_prefix=command_prefix,
            mention_trigger=mention_trigger,
            allowed_guild_ids=allowed_guild_ids,
            intents=intents,
        )

    async def start(self) -> None:
        await self._client.start(self._token)

    async def close(self) -> None:
        await self._client.close()


class _InnerClient(discord.Client):
    def __init__(
        self,
        adapter: DiscordAdapter,
        command_prefix: str,
        mention_trigger: bool,
        allowed_guild_ids: set[int],
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._adapter = adapter
        self._command_prefix = command_prefix
        self._mention_trigger = mention_trigger
        self._allowed_guild_ids = allowed_guild_ids

    async def on_ready(self) -> None:
        metrics.log_event(
            "startup", message=f"discord logged in as {self.user} ({self.user.id})"
        )

    def _extract_text(self, message: discord.Message) -> str | None:
        content = message.content
        if content.startswith(self._command_prefix):
            return content[len(self._command_prefix) :].strip()
        if self._mention_trigger and self.user in message.mentions:
            return content.replace(f"<@{self.user.id}>", "").strip()
        return None

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if (
            self._allowed_guild_ids
            and message.guild
            and message.guild.id not in self._allowed_guild_ids
        ):
            return

        text = self._extract_text(message)
        if text is None or self._adapter.on_message is None:
            return

        async def reply(text_out: str) -> None:
            for i in range(0, len(text_out), MAX_DISCORD_MESSAGE):
                await message.reply(text_out[i : i + MAX_DISCORD_MESSAGE])

        incoming = IncomingMessage(
            platform="discord",
            channel_id=str(message.channel.id),
            guild_id=str(message.guild.id) if message.guild else None,
            content=text,
            reply=reply,
            typing_cm=message.channel.typing,
        )
        await self._adapter.on_message(incoming)
