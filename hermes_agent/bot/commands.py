"""Platform-agnostic command router.

Both the Discord and Revolt adapters call `CommandRouter.handle()` with the
same IncomingMessage shape (see hermes_agent/adapters/base.py), so this is
the one place command behavior is defined, regardless of which chat
platform a message arrived from.

Commands:
  <prefix>summarize <youtube-url>  -> fetch transcript, generate a note, reply with proof-of-work
  <prefix>task <title>             -> create a tracked task entry, no note generation
  <prefix><anything else>          -> plain chat, forwarded to the LLM (original behavior)
"""

from __future__ import annotations

import asyncio
import time

from openai import APIError, OpenAI

from .. import metrics
from ..adapters.base import IncomingMessage
from ..config import Settings
from ..health import estimate_tokens
from ..services.notes_service import NotesService
from ..services.task_db import TaskDB
from ..services.transcript_service import NoTranscriptAvailable, TranscriptService
from ..soul import load_soul
from ..tools import WorkspaceError, WorkspaceTools


class CommandRouter:
    def __init__(
        self,
        settings: Settings,
        tools: WorkspaceTools,
        task_db: TaskDB,
        transcript_service: TranscriptService,
        notes_service: NotesService,
    ) -> None:
        self.settings = settings
        self.tools = tools
        self.task_db = task_db
        self.transcript_service = transcript_service
        self.notes_service = notes_service
        self.llm = OpenAI(base_url=settings.llm_api_base, api_key=settings.llm_api_key)

        self.system_prompt, self.soul_loaded = load_soul(settings.soul_path)
        metrics.log_event(
            "soul_loaded",
            message=(
                f"soul.md loaded from {settings.soul_path}"
                if self.soul_loaded
                else f"soul.md not found at {settings.soul_path} — using built-in default persona"
            ),
            soul_loaded=int(self.soul_loaded),
            soul_chars=len(self.system_prompt),
        )

    async def handle(self, message: IncomingMessage) -> None:
        text = message.content.strip()
        lowered = text.lower()

        if lowered.startswith("summarize "):
            await self._handle_summarize(message, text[len("summarize ") :].strip())
            return

        if lowered.startswith("task "):
            await self._handle_task(message, text[len("task ") :].strip())
            return

        await self._handle_chat(message, text)

    # --- plain chat (original behavior, now platform-agnostic) ---

    async def _handle_chat(self, message: IncomingMessage, prompt: str) -> None:
        with metrics.task_latency(guild_id=message.guild_id):
            try:
                async with message.typing_cm():
                    reply_text = await asyncio.to_thread(
                        self._call_llm, prompt, message.guild_id
                    )
            except APIError as exc:
                # Plain chat has no truncation guard the way the summarize/task pipeline's
                # transcripts do (see NotesService's MAX_TRANSCRIPT_CHARS) — a single very
                # long message can overflow the model's context window. This is an accepted,
                # visible gap rather than a silent one: it's distinguished from a generic
                # API error here so it shows up as its own error_type in the health
                # dashboard instead of blending into "something went wrong with the LLM".
                if "context" in str(exc).lower() or "maximum context length" in str(exc).lower():
                    metrics.log_error("llm_context_overflow", str(exc))
                    await message.reply(
                        "Sorry, that message is too long for the model's context window — "
                        "try a shorter message."
                    )
                    return
                metrics.log_error("llm_api_error", str(exc))
                await message.reply("Sorry, the LLM backend returned an error. Check the logs.")
                return
            except WorkspaceError as exc:
                metrics.log_error("workspace_error", str(exc))
                await message.reply(f"Tool error: {exc}")
                return
            except Exception as exc:  # noqa: BLE001 - last-resort guard, always logged
                metrics.log_error("unhandled_exception", str(exc))
                await message.reply("Sorry, something went wrong. Check the logs.")
                return

        await message.reply(reply_text)

    def _call_llm(self, prompt: str, guild_id: str | None) -> str:
        estimated_tokens = estimate_tokens(self.system_prompt, prompt)
        metrics.log_context_usage(
            context_pct=estimated_tokens / self.settings.llm_context_window * 100,
            guild_id=guild_id,
        )
        response = self.llm.chat.completions.create(
            model=self.settings.llm_model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            max_tokens=self.settings.llm_max_tokens,
            temperature=self.settings.llm_temperature,
            timeout=self.settings.llm_timeout,
        )
        usage = response.usage
        if usage:
            metrics.log_token_usage(
                tokens_prompt=usage.prompt_tokens,
                tokens_completion=usage.completion_tokens,
                guild_id=guild_id,
            )
        return response.choices[0].message.content or "(empty response)"

    # --- task tracking ---

    async def _handle_task(self, message: IncomingMessage, title: str) -> None:
        if not title:
            await message.reply("Usage: `task <title>`")
            return
        task_id = self.task_db.create_task(title)
        metrics.log_event("task_status_change", task_id=task_id, task_status="Backlog")
        await message.reply(f'[Task Created] Task ID #{task_id}: "{title}" (status: Backlog)')

    # --- transcript -> note pipeline ---

    async def _handle_summarize(self, message: IncomingMessage, url: str) -> None:
        if not url:
            await message.reply("Usage: `summarize <youtube-url>`")
            return

        task_id = self.task_db.create_task(f"Summarize: {url}")
        self.task_db.update_status(task_id, "In Progress")
        metrics.log_event("task_status_change", task_id=task_id, task_status="In Progress")
        await message.reply(f'[Task Queued] Task ID #{task_id} created — processing "{url}"...')

        # Reply has already been sent; the actual work happens in the background so
        # the bot's message-handling loop isn't blocked for however long this takes.
        asyncio.create_task(self._process_summarize(message, task_id, url))

    async def _process_summarize(
        self, message: IncomingMessage, task_id: int, url: str
    ) -> None:
        start = time.monotonic()

        try:
            transcript = await asyncio.to_thread(
                self.transcript_service.fetch_transcript, url
            )
        except NoTranscriptAvailable as exc:
            self.task_db.update_status(task_id, "Failed")
            metrics.log_event("task_status_change", task_id=task_id, task_status="Failed")
            await message.reply(f"[Task #{task_id} Failed] {exc}")
            return
        except Exception as exc:  # noqa: BLE001 - any yt-dlp/network failure
            metrics.log_error("transcript_fetch_error", str(exc))
            self.task_db.update_status(task_id, "Failed")
            metrics.log_event("task_status_change", task_id=task_id, task_status="Failed")
            await message.reply(f"[Task #{task_id} Failed] Could not fetch transcript — check the logs.")
            return

        try:
            note_path, word_count = await asyncio.to_thread(
                self.notes_service.generate_note, task_id, url, transcript
            )
        except Exception as exc:  # noqa: BLE001 - any LLM/filesystem failure
            metrics.log_error("note_generation_error", str(exc))
            self.task_db.update_status(task_id, "Failed")
            metrics.log_event("task_status_change", task_id=task_id, task_status="Failed")
            await message.reply(f"[Task #{task_id} Failed] Note generation failed — check the logs.")
            return

        elapsed_s = round(time.monotonic() - start, 1)
        self.task_db.update_status(task_id, "Completed", note_path=str(note_path))
        metrics.log_event(
            "task_status_change", task_id=task_id, task_status="Completed"
        )
        metrics.log_event(
            "note_generated",
            task_id=task_id,
            word_count=word_count,
            latency_ms=elapsed_s * 1000,
        )
        await message.reply(
            f"[Task #{task_id} Completed] Note saved: `{note_path.name}` | "
            f"{word_count} words | {elapsed_s}s"
        )
