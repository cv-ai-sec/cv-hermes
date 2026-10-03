"""Loads Hermes's persona/system-prompt from config/soul.md.

Previously this was a single hardcoded string in bot/commands.py. Pulling it into its
own file makes the persona editable without touching code, and lets the health
heartbeat (see health.py) report whether it actually loaded from disk or fell back to
the built-in default — a silently-reverted-to-default persona is exactly the kind of
thing that should show up in the health dashboard, not just be invisible.
"""

from __future__ import annotations

from pathlib import Path

DEFAULT_SOUL = (
    "You are Hermes, a helpful assistant running in a sandboxed lab environment. "
    "You have no access outside your workspace directory and no tools beyond the "
    "ones explicitly provided to you."
)


def load_soul(path: str) -> tuple[str, bool]:
    """Returns (system_prompt, loaded_from_file).

    Falls back to DEFAULT_SOUL if the file is missing or empty — a missing soul.md
    should degrade to a working (if generic) bot, not crash startup.
    """
    soul_path = Path(path)
    if soul_path.exists():
        text = soul_path.read_text(encoding="utf-8").strip()
        if text:
            return text, True
    return DEFAULT_SOUL, False
