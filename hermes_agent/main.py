"""Hermes Agent: a sandboxed Discord bot backed by an OpenAI-compatible LLM endpoint.

Responds to a configured prefix command and/or @mentions, forwards the
message to the configured LLM backend, and logs structured events (latency,
token usage, tool calls, errors) for the Loki/Grafana stack running
alongside it in docker-compose.yml.
"""

import asyncio

import discord
from openai import APIError, OpenAI

from . import metrics
from .config import Settings
from .tools import WorkspaceError, WorkspaceTools

MAX_DISCORD_MESSAGE = 2000


def build_system_prompt() -> str:
    return (
        "You are Hermes, a helpful assistant running in a sandboxed lab environment. "
        "You have no access outside your workspace directory and no tools beyond the "
        "ones explicitly provided to you."
    )


class HermesClient(discord.Client):
    def __init__(self, settings: Settings, **kwargs) -> None:
        super().__init__(**kwargs)
        self.settings = settings
        self.llm = OpenAI(base_url=settings.llm_api_base, api_key=settings.llm_api_key)
        self.tools = WorkspaceTools(
            root=settings.workspace_root,
            max_file_bytes=settings.max_file_bytes,
            allowed_tools=settings.allowed_tools,
        )

    async def on_ready(self) -> None:
        metrics.log_event("startup", message=f"logged in as {self.user} ({self.user.id})")

    def _is_addressed(self, message: discord.Message) -> str | None:
        content = message.content
        if content.startswith(self.settings.command_prefix):
            return content[len(self.settings.command_prefix):].strip()
        if self.settings.mention_trigger and self.user in message.mentions:
            return content.replace(f"<@{self.user.id}>", "").strip()
        return None

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        if (
            self.settings.allowed_guild_ids
            and message.guild
            and message.guild.id not in self.settings.allowed_guild_ids
        ):
            return

        prompt = self._is_addressed(message)
        if not prompt:
            return

        guild_id = message.guild.id if message.guild else None

        with metrics.task_latency(guild_id=guild_id):
            try:
                async with message.channel.typing():
                    reply = await asyncio.to_thread(self._call_llm, prompt, guild_id)
            except APIError as exc:
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

        for i in range(0, len(reply), MAX_DISCORD_MESSAGE):
            await message.reply(reply[i : i + MAX_DISCORD_MESSAGE])

    def _call_llm(self, prompt: str, guild_id: int | None) -> str:
        response = self.llm.chat.completions.create(
            model=self.settings.llm_model,
            messages=[
                {"role": "system", "content": build_system_prompt()},
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


def main() -> None:
    settings = Settings()
    settings.validate()
    metrics.configure_logging(settings.log_level, settings.log_file)

    intents = discord.Intents.default()
    intents.message_content = True

    client = HermesClient(settings, intents=intents)
    client.run(settings.discord_token, log_handler=None)


if __name__ == "__main__":
    main()
