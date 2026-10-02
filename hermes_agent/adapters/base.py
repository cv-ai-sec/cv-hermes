"""Chat-platform adapter interface.

Both Discord and Revolt are wired through this same shape so
hermes_agent/bot/commands.py contains the actual command logic exactly
once, platform-agnostic. Adding a third chat platform later means writing
one new adapter module, not touching command logic at all.
"""

from __future__ import annotations

import contextlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Awaitable, Callable


def _no_typing_indicator():
    return contextlib.nullcontext()


@dataclass
class IncomingMessage:
    platform: str  # "discord" | "revolt"
    channel_id: str
    guild_id: str | None
    content: str
    reply: Callable[[str], Awaitable[None]]
    # Async context manager shown while a reply is being generated (e.g. Discord's
    # "typing..." indicator). Defaults to a no-op for platforms without one.
    typing_cm: Callable[[], contextlib.AbstractAsyncContextManager] = field(
        default=_no_typing_indicator
    )


MessageHandler = Callable[[IncomingMessage], Awaitable[None]]


class ChatAdapter(ABC):
    """One instance per chat platform. `on_message` is assigned once by
    main.py before `start()` is awaited."""

    name: str

    def __init__(self) -> None:
        self.on_message: MessageHandler | None = None

    @abstractmethod
    async def start(self) -> None:
        """Connect and run until cancelled/closed."""

    @abstractmethod
    async def close(self) -> None:
        """Disconnect cleanly."""
