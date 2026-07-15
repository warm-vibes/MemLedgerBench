from __future__ import annotations

import json
import hashlib
import math
import os
import queue
import shlex
import subprocess
import threading
from abc import ABC, abstractmethod
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from .text import tokenize


@dataclass(slots=True)
class MemoryResponse:
    answer: str = ""
    retrieved_event_ids: list[str] = field(default_factory=list)
    decision: str = "answer"
    confidence: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "MemoryResponse":
        if not isinstance(raw, dict):
            raise ValueError("adapter response must be a JSON object")
        retrieved = raw.get("retrieved_event_ids", [])
        if not isinstance(retrieved, list):
            raise ValueError("retrieved_event_ids must be a list")
        decision = str(raw.get("decision", "answer"))
        if decision not in {"answer", "abstain", "deny", "clarify"}:
            raise ValueError(f"invalid adapter decision {decision!r}")
        confidence = float(raw["confidence"]) if raw.get("confidence") is not None else None
        if confidence is not None and not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        metadata = raw.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ValueError("response metadata must be an object")
        return cls(
            answer=str(raw.get("answer", "")),
            retrieved_event_ids=[str(item) for item in retrieved],
            decision=decision,
            confidence=confidence,
            metadata=dict(metadata),
        )


class MemoryAdapter(ABC):
    name = "adapter"

    @abstractmethod
    def reset(self, scenario: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def ingest(self, event: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def answer(self, query: dict[str, Any]) -> MemoryResponse:
        raise NotImplementedError

    def snapshot(self) -> Any:
        return None

    def restore(self, snapshot: Any) -> None:
        del snapshot

    def stats(self) -> dict[str, Any]:
        return {}

    def config(self) -> dict[str, Any]:
        return {}

    def close(self) -> None:
        return None


class LexicalAdapter(MemoryAdapter):
    """Dependency-free BM25 baseline.

    It indexes only ``observed_text``. Canonical voice transcripts and benchmark
    annotations stay hidden, so ASR corruption is measured rather than bypassed.
    """

    def __init__(self, *, top_k: int = 5, policy_aware: bool = True):
        if top_k < 1:
            raise ValueError("top_k must be at least 1")
        self.top_k = top_k
        self.policy_aware = policy_aware
        self.name = "bm25-policy" if policy_aware else "bm25-unsafe"
        self.scenario: dict[str, Any] | None = None
        self.policy: _OnlinePolicy | None = None
        self.events: list[dict[str, Any]] = []

    def reset(self, scenario: dict[str, Any]) -> None:
        self.scenario = dict(scenario)
        self.policy = _OnlinePolicy(scenario)
        self.events = []

    def ingest(self, event: dict[str, Any]) -> None:
        copied = dict(event)
        if copied.get("type") == "edit":
            target_id = str(copied["target_event_id"])
            target = next(
                (
                    existing
                    for existing in reversed(self.events)
                    if str(existing.get("id")) == target_id
                    and existing.get("type") == "message"
                ),
                None,
            )
            if target is None:
                raise RuntimeError(f"edit targets an unknown message {target_id!r}")
            target["observed_text"] = str(copied["observed_text"])
        self.events.append(copied)
        if self.policy is None:
            raise RuntimeError("adapter must be reset before ingest")
        self.policy.ingest(copied)

    def snapshot(self) -> Any:
        return [dict(event) for event in self.events]

    def restore(self, snapshot: Any) -> None:
        if self.scenario is None:
            raise RuntimeError("adapter must be reset before restore")
        restored = [dict(event) for event in (snapshot or [])]
        self.events = []
        self.policy = _OnlinePolicy(self.scenario)
        for event in restored:
            self.ingest(event)

    def answer(self, query: dict[str, Any]) -> MemoryResponse:
        if self.scenario is None or self.policy is None:
            raise RuntimeError("adapter must be reset before use")
        recipients = {str(query["requester_id"]), *map(str, query.get("audience_ids", []))}
        messages = [event for event in self.events if event.get("type") == "message"]
        ranked = _bm25_rank(str(query["question"]), messages)
        if self.policy_aware:
            at_seq = int(query["after_seq"])
            permitted = [
                (score, event)
                for score, event in ranked
                if self.policy.audience_can_view(event, recipients, at_seq)
            ]
            if ranked and (not permitted or ranked[0][1] is not permitted[0][1]):
                return MemoryResponse(
                    answer="I cannot share that memory with this audience.",
                    decision="deny",
                    retrieved_event_ids=[],
                )
            ranked = permitted
        selected = [event for _, event in ranked[: self.top_k]]
        if not selected:
            return MemoryResponse(
                answer="I cannot answer from the available memory.",
                decision="abstain",
                retrieved_event_ids=[],
            )
        return MemoryResponse(
            answer=" ".join(str(event.get("observed_text", "")) for event in selected),
            decision="answer",
            retrieved_event_ids=[str(event["id"]) for event in selected],
        )

    def stats(self) -> dict[str, Any]:
        messages = [event for event in self.events if event.get("type") == "message"]
        return {
            "indexed_messages": len(messages),
            "indexed_text_bytes": sum(
                len(str(event.get("observed_text", "")).encode("utf-8")) for event in messages
            ),
        }

    def config(self) -> dict[str, Any]:
        return {"top_k": self.top_k, "policy_aware": self.policy_aware}


class _OnlinePolicy:
    """Policy baseline derived only from scenario rules and already ingested events."""

    def __init__(self, scenario: dict[str, Any]):
        self.policies = {
            str(space["id"]): str(space["history_policy"])
            for space in scenario.get("spaces", [])
        }
        self.memberships: dict[tuple[str, str], list[tuple[int, bool]]] = defaultdict(list)
        self.deleted: dict[str, int] = {}
        self.policy_changes: dict[str, list[tuple[int, str]]] = defaultdict(list)

    def ingest(self, event: dict[str, Any]) -> None:
        event_type = event.get("type")
        if event_type == "membership":
            key = (str(event["space_id"]), str(event["user_id"]))
            self.memberships[key].append((int(event["seq"]), event.get("action") == "join"))
        elif event_type == "delete":
            target = str(event["target_event_id"])
            seq = int(event["seq"])
            self.deleted[target] = min(seq, self.deleted.get(target, seq))
        elif event_type == "policy_change":
            self.policy_changes[str(event["space_id"])].append(
                (int(event["seq"]), str(event["history_policy"]))
            )

    def history_policy(self, space_id: str, at_seq: int) -> str | None:
        policy = self.policies.get(space_id)
        for seq, changed_policy in self.policy_changes.get(space_id, []):
            if seq > at_seq:
                break
            policy = changed_policy
        return policy

    def is_deleted(self, event_id: str, at_seq: int) -> bool:
        deleted_at = self.deleted.get(event_id)
        return deleted_at is not None and deleted_at <= at_seq

    def is_member(self, user_id: str, space_id: str, at_seq: int) -> bool:
        active = False
        for seq, new_state in self.memberships.get((space_id, user_id), []):
            if seq > at_seq:
                break
            active = new_state
        return active

    def audience_can_view(
        self, event: dict[str, Any], recipients: set[str], at_seq: int
    ) -> bool:
        if (
            not recipients
            or self.is_deleted(str(event["id"]), at_seq)
            or int(event["seq"]) > at_seq
        ):
            return False
        space_id = str(event["space_id"])
        policy = self.history_policy(space_id, at_seq)
        if policy == "public":
            return True
        for user_id in recipients:
            at_message = self.is_member(user_id, space_id, int(event["seq"]))
            at_query = self.is_member(user_id, space_id, at_seq)
            if policy == "retain_seen" and not at_message:
                return False
            if policy == "active_window" and not (at_message and at_query):
                return False
            if policy == "current_full" and not at_query:
                return False
            if policy not in {"retain_seen", "active_window", "current_full"}:
                return False
        return True


def _bm25_rank(
    question: str, messages: list[dict[str, Any]], *, k1: float = 1.5, b: float = 0.75
) -> list[tuple[float, dict[str, Any]]]:
    if not messages:
        return []
    query_terms = tokenize(question, drop_stopwords=True)
    if not query_terms:
        query_terms = tokenize(question)
    documents = [tokenize(str(event.get("observed_text", ""))) for event in messages]
    average_length = sum(map(len, documents)) / max(1, len(documents))
    document_frequency: Counter[str] = Counter()
    for tokens in documents:
        document_frequency.update(set(tokens))

    ranked: list[tuple[float, dict[str, Any]]] = []
    count = len(documents)
    for event, tokens in zip(messages, documents, strict=True):
        frequencies = Counter(tokens)
        score = 0.0
        for term in query_terms:
            frequency = frequencies.get(term, 0)
            if not frequency:
                continue
            df = document_frequency[term]
            inverse_document_frequency = math.log(1 + (count - df + 0.5) / (df + 0.5))
            denominator = frequency + k1 * (
                1 - b + b * len(tokens) / max(1.0, average_length)
            )
            score += inverse_document_frequency * frequency * (k1 + 1) / denominator
        if score > 0:
            ranked.append((score, event))
    ranked.sort(key=lambda pair: (pair[0], int(pair[1]["seq"])), reverse=True)
    return ranked


class JsonlCommandAdapter(MemoryAdapter):
    """Adapter for any product stack that implements the JSONL protocol.

    One request and one response occupy one line. Requests use ``op`` values
    ``reset``, ``ingest``, ``query``, ``snapshot``, ``restore``, and ``stats``.
    Gold labels are never sent to the subprocess.
    """

    name = "jsonl-command"

    def __init__(self, command: str | list[str], *, timeout_seconds: float = 30.0):
        if isinstance(command, str):
            command = shlex.split(command, posix=os.name != "nt")
        if not command:
            raise ValueError("command cannot be empty")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.command = command
        self.timeout_seconds = timeout_seconds
        self.process: subprocess.Popen[str] | None = None

    def _start(self) -> None:
        if self.process and self.process.poll() is None:
            return
        self.process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )

    def _rpc(self, request: dict[str, Any]) -> dict[str, Any]:
        self._start()
        if self.process is None or not self.process.stdin or not self.process.stdout:
            raise RuntimeError("adapter subprocess failed to start")
        self.process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
        self.process.stdin.flush()
        lines: queue.Queue[str | BaseException] = queue.Queue(maxsize=1)

        def read_line() -> None:
            try:
                lines.put(self.process.stdout.readline())
            except BaseException as error:
                lines.put(error)

        threading.Thread(target=read_line, daemon=True).start()
        try:
            outcome = lines.get(timeout=self.timeout_seconds)
        except queue.Empty as error:
            self.process.kill()
            self.process.wait(timeout=5)
            raise TimeoutError(
                f"adapter timed out after {self.timeout_seconds:g}s during {request.get('op')!r}"
            ) from error
        if isinstance(outcome, BaseException):
            raise RuntimeError("failed to read adapter response") from outcome
        line = outcome
        if not line:
            raise RuntimeError("adapter exited without a response; see its standard-error output")
        response = json.loads(line)
        if not isinstance(response, dict):
            raise RuntimeError("adapter response must be a JSON object")
        if response.get("error"):
            raise RuntimeError(f"adapter error: {response['error']}")
        return response

    def reset(self, scenario: dict[str, Any]) -> None:
        _require_ack(self._rpc({"op": "reset", "scenario": scenario}), "reset")

    def ingest(self, event: dict[str, Any]) -> None:
        _require_ack(self._rpc({"op": "ingest", "event": event}), "ingest")

    def answer(self, query: dict[str, Any]) -> MemoryResponse:
        public_query = {
            key: query[key]
            for key in (
                "id",
                "after_seq",
                "requester_id",
                "audience_ids",
                "active_space_id",
                "purpose",
                "question",
            )
            if key in query
        }
        return MemoryResponse.from_mapping(self._rpc({"op": "query", "query": public_query}))

    def snapshot(self) -> Any:
        return self._rpc({"op": "snapshot"}).get("snapshot")

    def restore(self, snapshot: Any) -> None:
        _require_ack(self._rpc({"op": "restore", "snapshot": snapshot}), "restore")

    def stats(self) -> dict[str, Any]:
        return dict(self._rpc({"op": "stats"}).get("stats", {}))

    def close(self) -> None:
        if not self.process:
            return
        try:
            if self.process.poll() is None:
                try:
                    self._rpc({"op": "close"})
                except Exception:
                    self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        finally:
            for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
                if stream and not stream.closed:
                    stream.close()
            self.process = None

    def config(self) -> dict[str, Any]:
        fingerprint = hashlib.sha256(
            json.dumps(self.command, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return {
            "command_executable": os.path.basename(self.command[0]),
            "command_fingerprint_sha256": fingerprint,
            "command_arguments_recorded": False,
            "timeout_seconds": self.timeout_seconds,
        }


def _require_ack(response: dict[str, Any], operation: str) -> None:
    if response.get("ok") is not True:
        raise RuntimeError(f"adapter did not acknowledge {operation!r}")
