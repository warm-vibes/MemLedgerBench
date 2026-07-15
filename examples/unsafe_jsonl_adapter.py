"""Minimal JSONL protocol example.

This example intentionally ignores membership and deletion policy. It exists only to demonstrate
integration and should fail the benchmark's deployment gate.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from typing import Any


events: list[dict[str, Any]] = []


def tokens(value: str) -> list[str]:
    return re.findall(r"\w+", value.casefold())


def respond(value: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False) + "\n")
    sys.stdout.flush()


for line in sys.stdin:
    try:
        request = json.loads(line)
        operation = request.get("op")
        if operation == "reset":
            events = []
            respond({"ok": True})
        elif operation == "ingest":
            events.append(request["event"])
            respond({"ok": True})
        elif operation == "query":
            query_tokens = Counter(tokens(request["query"]["question"]))
            ranked: list[tuple[int, dict[str, Any]]] = []
            for event in events:
                if event.get("type") != "message":
                    continue
                score = sum((query_tokens & Counter(tokens(event.get("observed_text", "")))).values())
                if score:
                    ranked.append((score, event))
            ranked.sort(key=lambda item: (item[0], item[1]["seq"]), reverse=True)
            selected = [event for _, event in ranked[:3]]
            respond(
                {
                    "decision": "answer" if selected else "abstain",
                    "answer": " ".join(event.get("observed_text", "") for event in selected),
                    "retrieved_event_ids": [event["id"] for event in selected],
                }
            )
        elif operation == "snapshot":
            respond({"snapshot": {"events": events}})
        elif operation == "restore":
            events = list(request.get("snapshot", {}).get("events", []))
            respond({"ok": True})
        elif operation == "stats":
            messages = [event for event in events if event.get("type") == "message"]
            respond({"stats": {"indexed_messages": len(messages)}})
        elif operation == "close":
            respond({"ok": True})
            break
        else:
            respond({"error": f"unknown operation: {operation}"})
    except Exception as error:  # Protocol examples should turn failures into JSON errors.
        respond({"error": str(error)})

