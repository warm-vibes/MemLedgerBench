from __future__ import annotations

import copy
import hashlib
import json
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .adapters import MemoryAdapter
from .dataset import BenchmarkDataset
from .policy import PolicyOracle
from .scoring import aggregate_scores, score_response


def run_benchmark(
    dataset: BenchmarkDataset,
    adapter: MemoryAdapter,
    *,
    repetitions: int = 1,
    perform_recovery: bool = True,
    responses_log: str | Path | None = None,
) -> dict[str, Any]:
    if repetitions < 1:
        raise ValueError("repetitions must be at least 1")
    dataset.validate()

    # Phase 1: replay the online timeline and record every adapter answer. Ground
    # truth (the policy oracle and gold-derived forbidden evidence) is deliberately
    # NOT touched here, so no answer can be scored against or influenced by it.
    collected, adapter_meta = _collect_responses(
        dataset, adapter, repetitions, perform_recovery
    )

    # The raw responses log is the artifact we rescore from: exactly what the
    # adapter emitted, keyed by query id, with no gold or scoring mixed in.
    if responses_log is not None:
        _write_responses_log(responses_log, collected)

    # Phase 2: with every answer locked, build ground truth and score. This ordering
    # is what makes the sealed track trustworthy; keep the two phases separate.
    scored, summary = _score_collected(dataset, collected, repetitions)

    return {
        "format_version": "0.2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scenario_id": dataset.scenario_id,
        "dataset_sha256": _dataset_hash(dataset),
        "dataset_metadata": {
            key: dataset.raw.get("metadata", {}).get(key)
            for key in ("scale", "seed", "source", "sealed")
            if key in dataset.raw.get("metadata", {})
        },
        "adapter": adapter_meta["name"],
        "run_config": {
            "repetitions": repetitions,
            "perform_recovery": perform_recovery,
            "adapter": adapter_meta["config"],
        },
        "summary": summary,
        "system_stats": adapter_meta["stats"],
        "responses": scored,
    }


def _collect_responses(
    dataset: BenchmarkDataset,
    adapter: MemoryAdapter,
    repetitions: int,
    perform_recovery: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Replay events and gather adapter answers without consulting ground truth."""

    queries_by_seq: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for query in dataset.queries:
        queries_by_seq[int(query["after_seq"])].append(query)

    collected: list[dict[str, Any]] = []
    public_scenario = dataset.public_scenario()
    try:
        adapter.reset(copy.deepcopy(public_scenario))
        _answer_queries(
            queries_by_seq.pop(0, []), adapter, repetitions, collected, dataset.scenario_id
        )
        for event in dataset.events:
            if event.get("type") == "checkpoint" and perform_recovery:
                snapshot = adapter.snapshot()
                adapter.reset(copy.deepcopy(public_scenario))
                adapter.restore(snapshot)
            else:
                adapter.ingest(_public_event(event))
            _answer_queries(
                queries_by_seq.pop(int(event["seq"]), []),
                adapter,
                repetitions,
                collected,
                dataset.scenario_id,
            )
        if queries_by_seq:
            remaining = sorted(queries_by_seq)
            raise RuntimeError(f"queries were not executed at sequences {remaining}")
        adapter_meta = {
            "name": adapter.name,
            "config": adapter.config(),
            "stats": adapter.stats(),
        }
        return collected, adapter_meta
    finally:
        adapter.close()


def _answer_queries(
    queries: list[dict[str, Any]],
    adapter: MemoryAdapter,
    repetitions: int,
    collected: list[dict[str, Any]],
    scenario_id: str,
) -> None:
    for query in sorted(queries, key=lambda item: str(item["id"])):
        for repetition in range(repetitions):
            started = time.perf_counter()
            response = adapter.answer(_public_query(query, scenario_id))
            latency_ms = (time.perf_counter() - started) * 1000
            collected.append(
                {
                    "query": query,
                    "raw_response": {
                        "answer": response.answer,
                        "retrieved_event_ids": response.retrieved_event_ids,
                        "decision": response.decision,
                        "confidence": response.confidence,
                        "metadata": response.metadata,
                    },
                    "latency_ms": latency_ms,
                    "repetition": repetition,
                }
            )


def _score_collected(
    dataset: BenchmarkDataset,
    collected: list[dict[str, Any]],
    repetitions: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build ground truth and score the already-recorded answers."""

    oracle = PolicyOracle(dataset)
    scored: list[dict[str, Any]] = []
    for item in collected:
        scoring_query = _with_derived_forbidden(
            item["query"], item["raw_response"], oracle, dataset
        )
        row = score_response(scoring_query, item["raw_response"], latency_ms=item["latency_ms"])
        row["repetition"] = item["repetition"]
        scored.append(row)
    summary = aggregate_scores(scored, repetitions=repetitions)
    return scored, summary


def _write_responses_log(path: str | Path, collected: list[dict[str, Any]]) -> None:
    """Write the raw adapter responses as JSONL for independent rescoring.

    One object per recorded answer: the query id it answered, the repetition, the
    measured latency, and the response fields exactly as the adapter returned them.
    No gold answers, evidence labels, or scoring are included.
    """

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for item in collected:
            record = {
                "query_id": item["query"]["id"],
                "repetition": item["repetition"],
                "latency_ms": item["latency_ms"],
                **item["raw_response"],
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _public_event(event: dict[str, Any]) -> dict[str, Any]:
    """Expose only product-observable event fields, using a schema allowlist."""

    common = {"seq", "id", "type"}
    by_type = {
        "membership": {"space_id", "user_id", "action", "reason", "role"},
        "message": {
            "space_id",
            "author_id",
            "modality",
            "observed_text",
            "thread_id",
            "reply_to",
            "mentions",
            "source_timestamp",
            "ingest_timestamp",
            "attachment_ref",
            "trust",
        },
        "delete": {"target_event_id", "requested_by", "scope"},
        "edit": {"target_event_id", "author_id", "modality", "observed_text"},
        "checkpoint": {"label"},
        "policy_change": {"space_id", "history_policy", "effective_mode"},
    }
    allowed = common | by_type.get(str(event.get("type")), set())
    return copy.deepcopy({key: value for key, value in event.items() if key in allowed})


def _public_query(query: dict[str, Any], scenario_id: str) -> dict[str, Any]:
    allowed = {
        "after_seq",
        "requester_id",
        "audience_ids",
        "active_space_id",
        "purpose",
        "question",
    }
    public = copy.deepcopy({key: value for key, value in query.items() if key in allowed})
    public["id"] = _opaque_query_id(scenario_id, str(query["id"]))
    return public


def _opaque_query_id(scenario_id: str, query_id: str) -> str:
    """Deterministic, non-semantic handle so the adapter cannot read a query's

    intent from labels such as ``q_deleted_memory``. Stable across runs to keep
    results reproducible; salted by scenario so handles do not correlate across
    scenarios.
    """

    digest = hashlib.sha256(f"{scenario_id}\x00{query_id}".encode("utf-8")).hexdigest()
    return f"q_{digest[:12]}"


def _with_derived_forbidden(
    query: dict[str, Any],
    response: dict[str, Any],
    oracle: PolicyOracle,
    dataset: BenchmarkDataset,
) -> dict[str, Any]:
    """Classify every returned ID with the evaluator-owned policy oracle."""

    enriched = copy.deepcopy(query)
    forbidden = dict(enriched.get("forbidden_evidence", {}))
    event_by_id = dataset.event_by_id()
    recipients = {
        str(query["requester_id"]),
        *(str(item) for item in query.get("audience_ids", [])),
    }
    at_seq = int(query["after_seq"])
    for raw_id in response.get("retrieved_event_ids", []):
        event_id = str(raw_id)
        if event_id in forbidden:
            continue
        event = event_by_id.get(event_id)
        if event is None:
            forbidden[event_id] = "unknown_evidence"
        elif int(event["seq"]) > at_seq:
            forbidden[event_id] = "future"
        elif event.get("type") != "message":
            forbidden[event_id] = "invalid_evidence"
        elif oracle.is_deleted(event_id, at_seq):
            forbidden[event_id] = "deleted"
        elif not oracle.audience_can_view(event_id, recipients, at_seq):
            forbidden[event_id] = "authorization"
    enriched["forbidden_evidence"] = forbidden
    return enriched


def _dataset_hash(dataset: BenchmarkDataset) -> str:
    canonical = json.dumps(
        dataset.raw, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
