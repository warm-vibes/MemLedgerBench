"""MemLedgerBench adapter example: Mem0 (https://github.com/mem0ai/mem0).

Integration example, not a leaderboard entry. It shows how a real memory
product wires into the JSONL protocol.

Division of responsibility (the same split the bundled `bm25-policy` control
uses, and the only fair one):

* Mem0 is the system under test — it does ingestion and semantic retrieval.
  Messages are added with Mem0's real fact-extraction pipeline (`infer=True`);
  each stored memory keeps the source event id in metadata so retrieved
  memories map back to benchmark event ids.
* The adapter owns the authorization gate. A memory product does not know the
  scenario's membership / deletion / audience rules, so the adapter
  reconstructs them online from the ingested event stream (no gold labels)
  using the benchmark's own `_OnlinePolicy`, and filters retrieval by
  requester ∩ every output recipient at query time. Without this, any store
  fails the deployment gate (see `bm25-unsafe`).

Requirements:
    pip install mem0ai
    export OPENAI_API_KEY=...        # gpt-4o-mini + text-embedding-3-small
Optional env: MEM0_LLM_MODEL (default gpt-4o-mini), MEM0_EMBED_MODEL
(default text-embedding-3-small), BENCH_TOP_K (default 5).

Run:
    PYTHONPATH=src python -m mem_ledger_bench run data/fixtures/tiny_social.json \
        --adapter command \
        --command "python examples/mem0_adapter.py" \
        --repetitions 3 --out results/mem0-tiny.json
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from mem_ledger_bench.adapters import _OnlinePolicy  # noqa: E402

from mem0 import Memory  # noqa: E402
from qdrant_client import QdrantClient  # noqa: E402

LLM_MODEL = os.environ.get("MEM0_LLM_MODEL", "gpt-4o-mini")
EMBED_MODEL = os.environ.get("MEM0_EMBED_MODEL", "text-embedding-3-small")
TOP_K = int(os.environ.get("BENCH_TOP_K", "5"))
NAMESPACE = "bench"


def log(msg: str) -> None:
    sys.stderr.write(f"[mem0_adapter] {msg}\n")
    sys.stderr.flush()


def respond(value: dict) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _new_memory() -> Memory:
    # in-memory Qdrant (no file lock, no shared migration store) + a private
    # history db, so one long-lived instance serves the whole process
    return Memory.from_config({
        "llm": {"provider": "openai", "config": {"model": LLM_MODEL, "temperature": 0}},
        "embedder": {"provider": "openai", "config": {"model": EMBED_MODEL}},
        "vector_store": {"provider": "qdrant", "config": {
            "client": QdrantClient(":memory:"), "collection_name": "bench"}},
        "history_db_path": tempfile.mktemp(suffix=".db"),
    })


class Mem0System:
    def __init__(self) -> None:
        self.mem = _new_memory()
        self.scenario: dict = {}
        self.policy: _OnlinePolicy | None = None
        self.events: dict[str, dict] = {}   # event_id -> message event (text + fields)
        self.all_events: list[dict] = []    # full ordered ingest log (for snapshot)
        self.ingest_calls = 0

    def _clear_store(self) -> None:
        try:
            self.mem.delete_all(user_id=NAMESPACE)
        except Exception as error:
            log(f"delete_all failed, rebuilding instance: {error}")
            self.mem = _new_memory()

    # -- lifecycle ---------------------------------------------------------
    def reset(self, scenario: dict) -> None:
        self.scenario = scenario or {}
        self.policy = _OnlinePolicy(self.scenario)
        self.events = {}
        self.all_events = []
        self.ingest_calls = 0
        self._clear_store()

    def ingest(self, event: dict) -> None:
        if self.policy is None:
            raise RuntimeError("reset before ingest")
        self.policy.ingest(event)
        self.all_events.append(dict(event))
        etype = event.get("type")
        if etype == "message":
            eid = str(event["id"])
            self.events[eid] = dict(event)
            self._add_to_mem0(eid, str(event.get("observed_text", "")))
        elif etype == "edit":
            target = str(event["target_event_id"])
            if target in self.events:
                self.events[target]["observed_text"] = str(event.get("observed_text", ""))
                self._add_to_mem0(target, str(event.get("observed_text", "")))
        # membership / delete / policy_change: policy-only (handled above)

    def _add_to_mem0(self, event_id: str, text: str) -> None:
        if not text.strip():
            return
        try:
            self.mem.add(
                [{"role": "user", "content": text}],
                user_id=NAMESPACE,
                metadata={"event_id": event_id},
                infer=True,
            )
            self.ingest_calls += 1
        except Exception as error:  # keep the protocol alive on a single bad add
            log(f"add failed for {event_id}: {error}")

    # -- recovery: dump/restore the Qdrant points directly (no LLM, no
    #    re-embedding) so it stays within the per-op timeout, plus the event
    #    log to rebuild the policy gate and answer-text store ---------------
    def snapshot(self):
        points = []
        try:
            client = self.mem.vector_store.client
            offset = None
            while True:
                batch, offset = client.scroll(
                    collection_name="bench", with_vectors=True, with_payload=True,
                    limit=1000, offset=offset)
                points.extend({"id": p.id, "vector": p.vector, "payload": p.payload} for p in batch)
                if offset is None:
                    break
        except Exception as error:
            log(f"snapshot scroll failed: {error}")
        return {"points": points, "events": [dict(e) for e in self.all_events]}

    def restore(self, snapshot) -> None:
        snapshot = snapshot or {}
        # rebuild policy + text store from the event log WITHOUT calling the LLM
        self.policy = _OnlinePolicy(self.scenario)
        self.events = {}
        self.all_events = []
        for ev in snapshot.get("events", []):
            self.policy.ingest(ev)
            self.all_events.append(dict(ev))
            if ev.get("type") == "message":
                self.events[str(ev["id"])] = dict(ev)
            elif ev.get("type") == "edit" and str(ev.get("target_event_id")) in self.events:
                self.events[str(ev["target_event_id"])]["observed_text"] = str(ev.get("observed_text", ""))
        # re-insert the vector points directly
        self._clear_store()
        points = snapshot.get("points", [])
        if points:
            try:
                from qdrant_client.models import PointStruct
                client = self.mem.vector_store.client
                client.upsert(collection_name="bench", points=[
                    PointStruct(id=p["id"], vector=p["vector"], payload=p["payload"]) for p in points])
            except Exception as error:
                log(f"restore upsert failed: {error}")

    # -- query -------------------------------------------------------------
    def query(self, query: dict) -> dict:
        if self.policy is None:
            raise RuntimeError("reset before query")
        recipients = {str(query["requester_id"]), *map(str, query.get("audience_ids", []))}
        at_seq = int(query["after_seq"])

        # Mem0 semantic retrieval → source event ids (dedup, keep best rank)
        ranked_ids: list[str] = []
        seen: set[str] = set()
        try:
            hits = self.mem.search(query["question"], filters={"user_id": NAMESPACE}, limit=25)
            results = hits.get("results", hits) if isinstance(hits, dict) else hits
            for h in results:
                eid = (h.get("metadata") or {}).get("event_id")
                if eid and eid in self.events and eid not in seen:
                    seen.add(eid)
                    ranked_ids.append(eid)
        except Exception as error:
            log(f"search failed: {error}")

        ranked_events = [self.events[e] for e in ranked_ids]
        permitted = [e for e in ranked_events
                     if self.policy.audience_can_view(e, recipients, at_seq)]

        # typed deny: top retrieval is blocked for this audience
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
                "ingest_model_calls": self.ingest_calls,
                "query_model_calls": 0,
                "llm_model": LLM_MODEL, "embed_model": EMBED_MODEL}


def main() -> None:
    system = Mem0System()
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
