#!/usr/bin/env python3
"""Tail and validate Hermes Agent's JSON log file.

This is a manual debugging aid, not part of the ingestion pipeline — Promtail
reads the same file directly and ships it to Loki. Use this script when a
dashboard panel looks empty or wrong, to check the raw log lines actually
match the schema config/promtail-config.yaml and dashboards/hermes-overview.json
expect.

Usage:
    python scripts/parse_metrics.py [path/to/hermes.jsonl]
    python scripts/parse_metrics.py --follow [path/to/hermes.jsonl]
"""

import argparse
import json
import sys
import time

EXPECTED_EVENTS = {"startup", "task_latency", "token_usage", "tool_call", "error", "log"}


def validate_line(line: str, line_no: int) -> list[str]:
    problems = []
    try:
        record = json.loads(line)
    except json.JSONDecodeError as exc:
        return [f"line {line_no}: not valid JSON ({exc})"]

    for field in ("timestamp", "level", "event", "message"):
        if field not in record:
            problems.append(f"line {line_no}: missing required field {field!r}")

    event = record.get("event")
    if event and event not in EXPECTED_EVENTS:
        problems.append(f"line {line_no}: unrecognized event {event!r} (not in {EXPECTED_EVENTS})")

    if event == "task_latency" and "latency_ms" not in record:
        problems.append(f"line {line_no}: task_latency event missing latency_ms")
    if event == "token_usage" and not {"tokens_prompt", "tokens_completion"} <= record.keys():
        problems.append(f"line {line_no}: token_usage event missing token fields")
    if event == "tool_call" and "tool_name" not in record:
        problems.append(f"line {line_no}: tool_call event missing tool_name")
    if event == "error" and "error_type" not in record:
        problems.append(f"line {line_no}: error event missing error_type")

    return problems


def process(path: str, follow: bool) -> int:
    problem_count = 0
    with open(path, "r", encoding="utf-8") as f:
        line_no = 0
        while True:
            line = f.readline()
            if not line:
                if not follow:
                    break
                time.sleep(0.5)
                continue
            line_no += 1
            line = line.strip()
            if not line:
                continue
            problems = validate_line(line, line_no)
            if problems:
                problem_count += len(problems)
                for p in problems:
                    print(p, file=sys.stderr)
            else:
                record = json.loads(line)
                print(f"OK  line {line_no}: event={record.get('event')} level={record.get('level')}")
    return problem_count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default="/var/log/hermes/hermes.jsonl")
    parser.add_argument("--follow", action="store_true", help="keep reading new lines, like tail -f")
    args = parser.parse_args()

    problem_count = process(args.path, args.follow)
    if problem_count:
        print(f"\n{problem_count} schema problem(s) found.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
