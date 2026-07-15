"""MemLedgerBench adapter example: Cognee (https://github.com/topoteretes/cognee).

Integration example, not a leaderboard entry.

Division of responsibility (same as the Mem0 example and the bundled
`bm25-policy` control):

* Cognee is the system under test. Each message is added with its benchmark
  event id as a `node_set` tag; Cognee builds its knowledge graph with
  `cognify()`, and `search(CHUNKS)` returns chunks whose `belongs_to_set`
  carries the source event id, so retrieval maps back to benchmark events.
* The adapter owns authorization: it reconstructs membership / deletion /
  audience rules online from the ingested event stream (no gold labels) with
  the benchmark's `_OnlinePolicy` and filters retrieval by requester ∩ every
  recipient at query time.

`cognify()` is expensive, so it runs once lazily when the first query arrives
after new ingests (not per query).

Requirements:
    pip install cognee
    export LLM_API_KEY=$OPENAI_API_KEY LLM_PROVIDER=openai LLM_MODEL=gpt-4o-mini
    export EMBEDDING_PROVIDER=openai EMBEDDING_MODEL=text-embedding-3-small EMBEDDING_DIMENSIONS=1536
Optional: BENCH_TOP_K (default 5).

Run (recovery disabled — cognify latency; see docs/example-results.md):
    PYTHONPATH=src python -m mem_ledger_bench run data/fixtures/tiny_social.json \
        --adapter command --command "python examples/cognee_adapter.py" \
        --repetitions 3 --no-recovery --timeout 300 --out results/cognee-tiny.json
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

# Cognee (alembic migrations, structured logging) prints to stdout, which would
# corrupt the JSONL protocol. Keep a private copy of the real stdout for
# protocol responses and redirect fd 1 -> stderr so all library noise is
# diagnostic-only. Do this BEFORE importing cognee.
_PROTOCOL_FD = os.dup(1)
os.dup2(2, 1)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from mem_ledger_bench.adapters import _OnlinePolicy  # noqa: E402

import cognee  # noqa: E402
from cognee.modules.search.types import SearchType  # noqa: E402

TOP_K = int(os.environ.get("BENCH_TOP_K", "5"))


def log(msg: str) -> None:
    sys.stderr.write(f"[cognee_adapter] {msg}\n")
    sys.stderr.flush()


def respond(value: dict) -> None:
    os.write(_PROTOCOL_FD, (json.dumps(value, ensure_ascii=False) + "\n").encode("utf-8"))


class CogneeSystem:
    def __init__(self) -> None:
        self.scenario: dict = {}
        self.policy: _OnlinePolicy | None = None
        self.events: dict[str, dict] = {}
        self.all_events: list[dict] = []
        self.dirty = False
        self.cognified = False

    async def _prune(self) -> None:
        await cognee.prune.prune_data()
        await cognee.prune.prune_system(metadata=True)

    def reset(self, scenario: dict) -> None:
        self.scenario = scenario or {}
        self.policy = _OnlinePolicy(self.scenario)
        self.events = {}
        self.all_events = []
        self.dirty = False
        self.cognified = False
        asyncio.run(self._prune())

    def ingest(self, event: dict) -> None:
        if self.policy is None:
            raise RuntimeError("reset before ingest")
        self.policy.ingest(event)
        self.all_events.append(dict(event))
        etype = event.get("type")
        if etype == "message":
            eid = str(event["id"])
            self.events[eid] = dict(event)
            self._add(eid, str(event.get("observed_text", "")))
        elif etype == "edit":
            target = str(event["target_event_id"])
            if target in self.events:
                self.events[target]["observed_text"] = str(event.get("observed_text", ""))
                self._add(target, str(event.get("observed_text", "")))

    def _add(self, event_id: str, text: str) -> None:
        if not text.strip():
            return
        try:
            asyncio.run(cognee.add(text, node_set=[event_id]))
            self.dirty = True
        except Exception as error:
            log(f"add failed for {event_id}: {error}")

    def _ensure_cognified(self) -> None:
        if self.dirty:
            try:
                asyncio.run(cognee.cognify())
                self.cognified = True
            except Exception as error:
                log(f"cognify failed: {error}")
            self.dirty = False

    def snapshot(self):
        return {"events": [dict(e) for e in self.all_events]}

    def restore(self, snapshot) -> None:
        snapshot = snapshot or {}
        self.policy = _OnlinePolicy(self.scenario)
        self.events = {}
        self.all_events = []
        asyncio.run(self._prune())
        self.dirty = False
        self.cognified = False
        for ev in snapshot.get("events", []):
            self.ingest(ev)

    def query(self, query: dict) -> dict:
        if self.policy is None:
            raise RuntimeError("reset before query")
        self._ensure_cognified()
        recipients = {str(query["requester_id"]), *map(str, query.get("audience_ids", []))}
        at_seq = int(query["after_seq"])

        ranked_ids: list[str] = []
        seen: set[str] = set()
        try:
            results = asyncio.run(cognee.search(
                query_type=SearchType.CHUNKS, query_text=str(query["question"])))
            for group in results:
                items = group.get("search_result", []) if isinstance(group, dict) else []
                for it in items:
                    for eid in (it.get("belongs_to_set") or []):
                        eid = str(eid)
                        if eid in self.events and eid not in seen:
                            seen.add(eid)
                            ranked_ids.append(eid)
        except Exception as error:
            log(f"search failed: {error}")

        ranked_events = [self.events[e] for e in ranked_ids]
        permitted = [e for e in ranked_events
                     if self.policy.audience_can_view(e, recipients, at_seq)]
        if ranked_events and (not permitted or ranked_events[0] is not permitted[0]):
            return {"decision": "deny",
                    "answer": "I cannot share that memory with this audience.",
                    "retrieved_event_ids": []}
        selected = permitted[:TOP_K]
        if not selected:
            return {"decision": "abstain",
                    "answer": "I cannot answer from the available memory.",
                    "retrieved_event_ids": []}
        return {"decision": "answer",
                "answer": " ".join(str(e.get("observed_text", "")) for e in selected),
                "retrieved_event_ids": [str(e["id"]) for e in selected]}

    def stats(self) -> dict:
        return {"indexed_messages": len(self.events),
                "cognified": self.cognified,
                "llm_model": os.environ.get("LLM_MODEL", "?"),
                "embed_model": os.environ.get("EMBEDDING_MODEL", "?")}


def main() -> None:
    system = CogneeSystem()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            op = request.get("op")
            if op == "reset":
                system.reset(request.get("scenario", {}))
                respond({"ok": True})
            elif op == "ingest":
                system.ingest(request["event"])
                respond({"ok": True})
            elif op == "query":
                respond(system.query(request["query"]))
            elif op == "snapshot":
                respond({"snapshot": system.snapshot()})
            elif op == "restore":
                system.restore(request.get("snapshot", {}))
                respond({"ok": True})
            elif op == "stats":
                respond({"stats": system.stats()})
            elif op == "close":
                respond({"ok": True})
                break
            else:
                respond({"error": f"unknown operation: {op}"})
        except Exception as error:
            respond({"error": str(error)})


if __name__ == "__main__":
    main()
