"""Hermes Agent entrypoint.

Wires one or both chat-platform adapters (Discord, optionally Revolt) to the
shared, platform-agnostic command router in hermes_agent/bot/commands.py.
Which adapters actually start depends only on which tokens are present in
.env — see config.py.
"""

from __future__ import annotations

import asyncio

from . import metrics
from .adapters.discord_adapter import DiscordAdapter
from .bot.commands import CommandRouter
from .config import Settings
from .services.notes_service import NotesService
from .services.task_db import TaskDB
from .services.transcript_service import TranscriptService
from .tools import WorkspaceTools


async def _run(settings: Settings) -> None:
    tools = WorkspaceTools(
        root=settings.workspace_root,
        max_file_bytes=settings.max_file_bytes,
        allowed_tools=settings.allowed_tools,
    )
    task_db = TaskDB(settings.task_db_path)
    transcript_service = TranscriptService()
    notes_service = NotesService(
        llm_api_base=settings.llm_api_base,
        llm_api_key=settings.llm_api_key,
        llm_model=settings.llm_model,
        llm_timeout=settings.llm_timeout,
        notes_dir=settings.notes_dir,
    )

    router = CommandRouter(
        settings=settings,
        tools=tools,
        task_db=task_db,
        transcript_service=transcript_service,
        notes_service=notes_service,
    )

    adapters = []

    if settings.discord_token:
        discord_adapter = DiscordAdapter(
            token=settings.discord_token,
            command_prefix=settings.command_prefix,
            mention_trigger=settings.mention_trigger,
            allowed_guild_ids=settings.allowed_guild_ids,
        )
        discord_adapter.on_message = router.handle
        adapters.append(discord_adapter)

    if settings.revolt_token:
        # Imported lazily so a Discord-only deployment never needs the revolt.py/
        # aiohttp dependency chain to actually import cleanly.
        from .adapters.revolt_adapter import RevoltAdapter

        revolt_adapter = RevoltAdapter(
            token=settings.revolt_token,
            command_prefix=settings.command_prefix,
            mention_trigger=settings.mention_trigger,
            allowed_channel_ids=settings.revolt_allowed_channel_ids,
        )
        revolt_adapter.on_message = router.handle
        adapters.append(revolt_adapter)

    if not adapters:
        raise RuntimeError(
            "No chat platform configured — set DISCORD_TOKEN and/or REVOLT_TOKEN in .env."
        )

    await asyncio.gather(*(adapter.start() for adapter in adapters))


def main() -> None:
    settings = Settings()
    settings.validate()
    metrics.configure_logging(settings.log_level, settings.log_file)
    asyncio.run(_run(settings))


if __name__ == "__main__":
    main()
