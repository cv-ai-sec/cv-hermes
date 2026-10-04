#!/usr/bin/env python3
"""Write sanitized per-session summaries for Loki.

Reads the agent's sessions.json and appends one JSON line per session to logs/sessions-summary.jsonl.
Only the fields in KEEP are written. Display names, routing keys, origins, and metadata are dropped,
and so are the request dumps, which contain conversation text. Run every few minutes from cron.
"""
import json
import time
from pathlib import Path

KEEP = (
    "session_id", "platform", "chat_type", "created_at", "updated_at",
    "input_tokens", "output_tokens", "total_tokens",
    "cache_read_tokens", "cache_write_tokens",
    "estimated_cost_usd", "cost_status",
    "was_auto_reset", "auto_reset_reason", "suspended",
    "resume_reason", "reset_had_activity",
)

DATA = Path(__file__).resolve().parent.parent / "hermes-data"
SESSIONS = DATA / "sessions" / "sessions.json"
OUT = DATA / "logs" / "sessions-summary.jsonl"


def main() -> None:
    sessions = json.loads(SESSIONS.read_text(encoding="utf-8"))
    now = int(time.time())
    with OUT.open("a", encoding="utf-8") as out:
        for key, value in sessions.items():
            if key.startswith("_") or not isinstance(value, dict):
                continue
            row = {"ts": now}
            row.update({field: value[field] for field in KEEP if field in value})
            out.write(json.dumps(row, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
