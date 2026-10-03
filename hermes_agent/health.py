"""Hermes's own health signal: is the soul loaded, is the LLM reachable, how full is
the context window running.

This is intentionally observational only — it never changes behavior (no auto-restart,
no fallback model), it just makes state that was previously invisible (soul.md load
status, LLM reachability, estimated context usage) show up in Grafana the same way
token usage and task latency already do, via the same Loki/Grafana pipeline.

Token/context estimates here are a rough heuristic (~4 characters per token), not a
real tokenizer call — good enough to flag "this is getting close to the configured
context window" without adding a tokenizer dependency per model. See
docs/ARCHITECTURE.md's "Hermes health" section for why that's an accepted
approximation.
"""

from __future__ import annotations

import asyncio
import time

from . import metrics


def estimate_tokens(*texts: str) -> int:
    return sum(len(t) for t in texts) // 4


async def heartbeat_loop(router, interval_seconds: int, adapter_names: list[str]) -> None:
    start = time.monotonic()
    while True:
        await asyncio.sleep(interval_seconds)
        llm_reachable = True
        try:
            await asyncio.to_thread(router.llm.models.list)
        except Exception:  # noqa: BLE001 - any backend-unreachable error collapses to False
            llm_reachable = False

        metrics.log_health_heartbeat(
            soul_loaded=router.soul_loaded,
            soul_chars=len(router.system_prompt),
            llm_reachable=llm_reachable,
            context_window=router.settings.llm_context_window,
            uptime_seconds=round(time.monotonic() - start, 1),
            adapters_active=",".join(adapter_names),
        )
