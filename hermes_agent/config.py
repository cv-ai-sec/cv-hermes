"""Loads non-secret config from YAML and secrets/overrides from environment variables.

Precedence: environment variable > hermes.yaml > hermes.example.yaml defaults.
Secrets (DISCORD_TOKEN, LLM_API_KEY) only ever come from the environment — they
are intentionally not readable from any YAML file, so a leaked config file can
never leak a credential.
"""

import os
from pathlib import Path

import yaml

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def _load_yaml() -> dict:
    for name in ("hermes.yaml", "hermes.example.yaml"):
        path = _CONFIG_DIR / name
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    return {}


class Settings:
    def __init__(self) -> None:
        yaml_cfg = _load_yaml()

        # --- Secrets: environment only, never from YAML ---
        self.discord_token = os.environ.get("DISCORD_TOKEN", "")
        self.revolt_token = os.environ.get("REVOLT_TOKEN", "")
        self.llm_api_key = os.environ.get("LLM_API_KEY", "")

        # --- Non-secret config: env override > yaml > hardcoded fallback ---
        self.log_level = os.environ.get("HERMES_LOG_LEVEL", yaml_cfg.get("log_level", "INFO"))
        self.log_file = yaml_cfg.get("log_file", "/var/log/hermes/hermes.jsonl")

        self.llm_api_base = os.environ.get("LLM_API_BASE", "http://localhost:11434/v1")
        self.llm_model = os.environ.get("LLM_MODEL", "")

        llm_cfg = yaml_cfg.get("llm", {})
        self.llm_timeout = llm_cfg.get("request_timeout_seconds", 60)
        self.llm_max_tokens = llm_cfg.get("max_tokens", 1024)
        self.llm_temperature = llm_cfg.get("temperature", 0.4)
        # Informational only — the context size of whatever model is actually loaded in
        # LM Studio (or whatever LLM_API_BASE points at). Not enforced or read back from
        # the backend (OpenAI-compatible APIs don't expose it generically), so this must
        # be kept in sync by hand with your loaded model. Used only to estimate % of
        # context used per call for the health heartbeat (see health.py) — never to
        # truncate or reject a request.
        self.llm_context_window = int(
            os.environ.get("LLM_CONTEXT_WINDOW", llm_cfg.get("context_window", 8192))
        )

        # Shared across every chat platform — a message is addressed the same way
        # whether it arrives via Discord or Revolt.
        chat_cfg = yaml_cfg.get("chat", {})
        self.command_prefix = chat_cfg.get("command_prefix", "!hermes ")
        self.mention_trigger = chat_cfg.get("mention_trigger", True)

        discord_cfg = yaml_cfg.get("discord", {})
        allowed = os.environ.get("DISCORD_ALLOWED_GUILD_IDS", "")
        if allowed.strip():
            self.allowed_guild_ids = {int(g) for g in allowed.split(",") if g.strip()}
        else:
            self.allowed_guild_ids = set(discord_cfg.get("allowed_guild_ids", []) or [])

        revolt_cfg = yaml_cfg.get("revolt", {})
        revolt_allowed = os.environ.get("REVOLT_ALLOWED_CHANNEL_IDS", "")
        if revolt_allowed.strip():
            self.revolt_allowed_channel_ids = {
                c.strip() for c in revolt_allowed.split(",") if c.strip()
            }
        else:
            self.revolt_allowed_channel_ids = set(
                revolt_cfg.get("allowed_channel_ids", []) or []
            )

        workspace_cfg = yaml_cfg.get("workspace", {})
        self.workspace_root = os.environ.get(
            "HERMES_WORKSPACE_DIR", workspace_cfg.get("root", "/workspace")
        )
        self.max_file_bytes = workspace_cfg.get("max_file_bytes", 5 * 1024 * 1024)

        self.allowed_tools = set((yaml_cfg.get("tools", {}) or {}).get("allowed", []))

        # --- Task automation pipeline (summarize/task commands) ---
        tasks_cfg = yaml_cfg.get("tasks", {})
        self.task_db_path = os.environ.get(
            "TASK_DB_PATH", tasks_cfg.get("db_path", "/app/data/tasks.db")
        )
        self.notes_dir = os.environ.get("NOTES_DIR", tasks_cfg.get("notes_dir", "/app/notes"))
        self.max_transcript_chars = int(
            os.environ.get(
                "MAX_TRANSCRIPT_CHARS", tasks_cfg.get("max_transcript_chars", 20000)
            )
        )

        # --- Hermes identity + health ---
        self.soul_path = os.environ.get(
            "SOUL_MD_PATH", yaml_cfg.get("soul_path", "/app/config/soul.md")
        )
        self.health_interval_seconds = int(
            os.environ.get("HEALTH_INTERVAL_SECONDS", yaml_cfg.get("health_interval_seconds", 300))
        )

        # --- Local web chat (bypasses Discord entirely) ---
        self.web_chat_enabled = os.environ.get("WEB_CHAT_ENABLED", "true").strip().lower() == "true"
        self.web_chat_port = int(os.environ.get("WEB_CHAT_PORT", "8503"))

    def validate(self) -> None:
        missing = [
            name
            for name, value in (("LLM_MODEL", self.llm_model),)
            if not value
        ]
        if missing:
            raise RuntimeError(
                f"Missing required settings: {', '.join(missing)}. "
                "Copy .env.example to .env and fill in real values."
            )
        if not self.discord_token and not self.revolt_token:
            raise RuntimeError(
                "No chat platform configured — set DISCORD_TOKEN and/or REVOLT_TOKEN in .env."
            )
