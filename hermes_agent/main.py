"""Hermes Agent entrypoint.

Wires chat-platform adapters to the shared, platform-agnostic command router
in hermes_agent/bot/commands.py. Which adapters actually start depends only
on which tokens are present in .env — see config.py.

Discord is fully supported. Revolt's adapter exists (hermes_agent/adapters/
revolt_adapter.py) but revolt.py is NOT currently installed (see
requirements.txt for why — a hard dependency conflict with openai, not a
decision to drop Revolt support permanently) — setting REVOLT_TOKEN without
it installed raises a clear RuntimeError below rather than an import crash.
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
        max_transcript_chars=settings.max_transcript_chars,
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
        # Imported lazily so a Discord-only deployment never needs revolt.py to actually
        # import cleanly. revolt.py is NOT currently in requirements.txt — its pinned
        # dependencies conflict with openai's (see the comment in requirements.txt for
        # the full story) — so this will raise ImportError until that's resolved. Fail
        # with a clear message here rather than a cryptic ModuleNotFoundError traceback.
        try:
            from .adapters.revolt_adapter import RevoltAdapter
        except ImportError as exc:
            raise RuntimeError(
                "REVOLT_TOKEN is set, but the revolt.py package isn't installed — it's "
                "deliberately excluded from requirements.txt due to a dependency conflict "
                "with openai (see the comment there). Either leave REVOLT_TOKEN unset to "
                "run Discord-only, or see requirements.txt for how to re-enable Revolt."
            ) from exc

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
