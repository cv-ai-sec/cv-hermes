"""Structured JSON event logging for Hermes Agent.

Every event is one JSON object per line, written to stdout and to
HERMES_LOG_FILE. Promtail tails the file and ships it to Loki; the field
names here (event, latency_ms, tokens_prompt, tokens_completion, tool_name,
error_type, task_id, task_status, word_count) are a contract with
config/promtail-config.yaml's pipeline stages and
dashboards/hermes-overview.json's queries — change a field name in both
places together.

Never pass raw user message content, tokens, or secrets into `extra` —
these lines get shipped verbatim into the lab's own Loki instance and then
viewed in Grafana, so anything written here should already be safe to show
on a shared screen.
"""

import json
import logging
import os
import sys
import time
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler

_logger = logging.getLogger("hermes")


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "event": getattr(record, "event", "log"),
            "message": record.getMessage(),
        }
        for key in (
            "latency_ms",
            "tokens_prompt",
            "tokens_completion",
            "tool_name",
            "error_type",
            "guild_id",
            "task_id",
            "task_status",
            "word_count",
            # --- Hermes health (see health.py) ---
            "soul_loaded",
            "soul_chars",
            "llm_reachable",
            "context_window",
            "context_pct",
            "uptime_seconds",
            "adapters_active",
        ):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        return json.dumps(payload, default=str)


def configure_logging(log_level: str = "INFO", log_file: str | None = None) -> None:
    _logger.setLevel(log_level.upper())
    _logger.handlers.clear()

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(_JsonFormatter())
    _logger.addHandler(stream_handler)

    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5
        )
        file_handler.setFormatter(_JsonFormatter())
        _logger.addHandler(file_handler)


def log_event(event: str, message: str = "", level: str = "INFO", **fields) -> None:
    _logger.log(
        getattr(logging, level.upper(), logging.INFO),
        message or event,
        extra={"event": event, **fields},
    )


def log_error(error_type: str, message: str) -> None:
    log_event("error", message=message, level="ERROR", error_type=error_type)


def log_tool_call(tool_name: str, guild_id: int | None = None) -> None:
    log_event("tool_call", message=f"tool call: {tool_name}", tool_name=tool_name, guild_id=guild_id)


def log_token_usage(tokens_prompt: int, tokens_completion: int, guild_id: int | None = None) -> None:
    log_event(
        "token_usage",
        message="llm token usage",
        tokens_prompt=tokens_prompt,
        tokens_completion=tokens_completion,
        guild_id=guild_id,
    )


def log_health_heartbeat(
    soul_loaded: bool,
    soul_chars: int,
    llm_reachable: bool,
    context_window: int,
    uptime_seconds: float,
    adapters_active: str,
) -> None:
    # Booleans logged as 1/0, not true/false — LogQL's `unwrap` (used by the Hermes
    # health Grafana panels) needs a numeric-parsable value, not a JSON boolean.
    log_event(
        "health_heartbeat",
        message="hermes health heartbeat",
        soul_loaded=int(soul_loaded),
        soul_chars=soul_chars,
        llm_reachable=int(llm_reachable),
        context_window=context_window,
        uptime_seconds=uptime_seconds,
        adapters_active=adapters_active,
    )


def log_context_usage(context_pct: float, guild_id: int | None = None) -> None:
    log_event(
        "context_usage",
        message="estimated context window usage",
        context_pct=round(context_pct, 1),
        guild_id=guild_id,
    )


@contextmanager
def task_latency(guild_id: int | None = None):
    """Usage: `with task_latency(guild_id=...): ...` — logs a task_latency event on exit."""
    start = time.monotonic()
    try:
        yield
    finally:
        elapsed_ms = round((time.monotonic() - start) * 1000, 1)
        log_event(
            "task_latency",
            message="task completed",
            latency_ms=elapsed_ms,
            guild_id=guild_id,
        )
