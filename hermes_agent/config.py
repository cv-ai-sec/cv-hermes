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

        discord_cfg = yaml_cfg.get("discord", {})
        self.command_prefix = discord_cfg.get("command_prefix", "!hermes ")
        self.mention_trigger = discord_cfg.get("mention_trigger", True)
        allowed = os.environ.get("DISCORD_ALLOWED_GUILD_IDS", "")
        if allowed.strip():
            self.allowed_guild_ids = {int(g) for g in allowed.split(",") if g.strip()}
        else:
            self.allowed_guild_ids = set(discord_cfg.get("allowed_guild_ids", []) or [])

        workspace_cfg = yaml_cfg.get("workspace", {})
        self.workspace_root = os.environ.get(
            "HERMES_WORKSPACE_DIR", workspace_cfg.get("root", "/workspace")
        )
        self.max_file_bytes = workspace_cfg.get("max_file_bytes", 5 * 1024 * 1024)

        self.allowed_tools = set((yaml_cfg.get("tools", {}) or {}).get("allowed", []))

    def validate(self) -> None:
        missing = [
            name
            for name, value in (
                ("DISCORD_TOKEN", self.discord_token),
                ("LLM_MODEL", self.llm_model),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                f"Missing required settings: {', '.join(missing)}. "
                "Copy .env.example to .env and fill in real values."
            )
