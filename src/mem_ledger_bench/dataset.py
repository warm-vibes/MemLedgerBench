from __future__ import annotations

import json
import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


HISTORY_POLICIES = {"public", "retain_seen", "active_window", "current_full"}
EVENT_TYPES = {"membership", "message", "delete", "edit", "checkpoint", "policy_change"}
FORBIDDEN_REASONS = {
    "authorization",
    "contextual_integrity",
    "deleted",
    "superseded",
    "untrusted_source",
    "future",
    "invalid_evidence",
    "unknown_evidence",
}


class DatasetValidationError(ValueError):
    """Raised when benchmark data is structurally or semantically invalid."""


@dataclass(slots=True)
class BenchmarkDataset:
    raw: dict[str, Any]

    @property
    def scenario_id(self) -> str:
        return str(self.raw["scenario_id"])

    @property
    def entities(self) -> list[dict[str, Any]]:
        return self.raw["entities"]

    @property
    def spaces(self) -> list[dict[str, Any]]:
        return self.raw["spaces"]

    @property
    def events(self) -> list[dict[str, Any]]:
        return self.raw["events"]

    @property
    def queries(self) -> list[dict[str, Any]]:
        return self.raw["queries"]

    def public_scenario(self) -> dict[str, Any]:
        """Scenario metadata safe to expose to a system under test.

        Gold answers, evidence labels, and future events are deliberately omitted.
        """

        entity_fields = {"id", "kind", "display_name", "aliases", "locale", "timezone", "roles"}
        space_fields = {"id", "kind", "display_name", "history_policy"}
        public = {
            "benchmark_version": self.raw["benchmark_version"],
            "scenario_id": self.scenario_id,
            "entities": [
                {key: value for key, value in entity.items() if key in entity_fields}
                for entity in self.entities
            ],
            "spaces": [
                {key: value for key, value in space.items() if key in space_fields}
                for space in self.spaces
            ],
            "metadata": {
                str(key).removeprefix("public_"): value
                for key, value in self.raw.get("metadata", {}).items()
                if str(key).startswith("public_")
            },
        }
        return copy.deepcopy(public)

    def event_by_id(self) -> dict[str, dict[str, Any]]:
        return {str(event["id"]): event for event in self.events}

    def validate(self, *, check_policy: bool = True) -> list[str]:
        if not isinstance(self.raw, dict):
            raise DatasetValidationError("dataset root must be a JSON object")
        errors: list[str] = []
        required_top = {
            "benchmark_version",
            "scenario_id",
            "entities",
            "spaces",
            "events",
            "queries",
        }
        missing = sorted(required_top - self.raw.keys())
        if missing:
            raise DatasetValidationError(f"missing top-level fields: {', '.join(missing)}")
        for field in ("entities", "spaces", "events", "queries"):
            value = self.raw.get(field)
            if not isinstance(value, list):
                errors.append(f"top-level field {field!r} must be a list")
            elif any(not isinstance(item, dict) for item in value):
                errors.append(f"every item in {field!r} must be an object")
        if not isinstance(self.raw.get("benchmark_version"), str):
            errors.append("benchmark_version must be a string")
        if not isinstance(self.raw.get("scenario_id"), str) or not self.raw.get("scenario_id"):
            errors.append("scenario_id must be a non-empty string")
        if errors:
            raise DatasetValidationError("\n".join(f"- {error}" for error in errors))

        entity_ids = _unique_ids(self.entities, "entity", errors)
        space_ids = _unique_ids(self.spaces, "space", errors)
        event_ids = _unique_ids(self.events, "event", errors)
        _unique_ids(self.queries, "query", errors)

        user_ids = {
            str(entity["id"])
            for entity in self.entities
            if entity.get("kind") == "user" and "id" in entity
        }
        if not user_ids:
            errors.append("at least one user entity is required")

        for space in self.spaces:
            policy = space.get("history_policy")
            if policy not in HISTORY_POLICIES:
                errors.append(
                    f"space {space.get('id')!r} has invalid history_policy {policy!r}"
                )

        previous_seq = -1
        event_seqs: set[int] = set()
        event_by_id: dict[str, dict[str, Any]] = {}
        membership_state: dict[tuple[str, str], bool] = {}
        for event in self.events:
            event_id = str(event.get("id", "<missing>"))
            event_type = event.get("type")
            seq = event.get("seq")
            if not isinstance(seq, int):
                errors.append(f"event {event_id!r} sequence must be an integer")
            elif seq < 1:
                errors.append(f"event {event_id!r} sequence must be at least 1")
            elif seq <= previous_seq:
                errors.append(f"event {event_id!r} sequence must be strictly increasing")
            else:
                previous_seq = seq
                event_seqs.add(seq)
            if event_type not in EVENT_TYPES:
                errors.append(f"event {event_id!r} has invalid type {event_type!r}")
            if event_type in {"membership", "message", "policy_change"}:
                if event.get("space_id") not in space_ids:
                    errors.append(f"event {event_id!r} references an unknown space")
            if event_type == "membership":
                if event.get("user_id") not in user_ids:
                    errors.append(f"membership {event_id!r} references an unknown user")
                if event.get("action") not in {"join", "leave"}:
                    errors.append(f"membership {event_id!r} action must be join or leave")
                else:
                    membership_key = (str(event.get("space_id")), str(event.get("user_id")))
                    active = membership_state.get(membership_key, False)
                    if event.get("action") == "join" and active:
                        errors.append(f"membership {event_id!r} joins an already active member")
                    if event.get("action") == "leave" and not active:
                        errors.append(f"membership {event_id!r} leaves an inactive member")
                    membership_state[membership_key] = event.get("action") == "join"
            elif event_type == "message":
                if event.get("author_id") not in user_ids:
                    errors.append(f"message {event_id!r} references an unknown author")
                if not isinstance(event.get("observed_text"), str):
                    errors.append(f"message {event_id!r} needs observed_text")
                if event.get("modality", "text") not in {"text", "voice", "image", "attachment"}:
                    errors.append(f"message {event_id!r} has an invalid modality")
            elif event_type in {"delete", "edit"}:
                target = str(event.get("target_event_id", ""))
                target_event = event_by_id.get(target)
                if not target_event or target_event.get("type") != "message":
                    errors.append(f"{event_type} {event_id!r} must target an earlier message")
                if event_type == "edit":
                    if event.get("author_id") not in user_ids:
                        errors.append(f"edit {event_id!r} references an unknown author")
                    if not isinstance(event.get("observed_text"), str):
                        errors.append(f"edit {event_id!r} needs replacement observed_text")
            elif event_type == "policy_change":
                if event.get("history_policy") not in HISTORY_POLICIES:
                    errors.append(f"policy change {event_id!r} has an invalid history_policy")
            event_by_id[event_id] = event

        max_seq = previous_seq
        for query in self.queries:
            query_id = str(query.get("id", "<missing>"))
            if query.get("requester_id") not in user_ids:
                errors.append(f"query {query_id!r} references an unknown requester")
            audience_ids = query.get("audience_ids", [])
            if not isinstance(audience_ids, list) or any(user not in user_ids for user in audience_ids):
                errors.append(f"query {query_id!r} has invalid audience_ids")
            after_seq = query.get("after_seq")
            if not isinstance(after_seq, int) or after_seq < 0 or after_seq > max_seq:
                errors.append(f"query {query_id!r} has invalid after_seq")
            elif after_seq != 0 and after_seq not in event_seqs:
                errors.append(f"query {query_id!r} after_seq does not match an event checkpoint")
            if query.get("active_space_id") not in space_ids:
                errors.append(f"query {query_id!r} references an unknown active space")
            if not isinstance(query.get("question"), str) or not query.get("question", "").strip():
                errors.append(f"query {query_id!r} needs a question")
            raw_gold = query.get("gold_evidence_ids", [])
            if not isinstance(raw_gold, list):
                errors.append(f"query {query_id!r} gold_evidence_ids must be a list")
                raw_gold = []
            raw_forbidden = query.get("forbidden_evidence", {})
            if not isinstance(raw_forbidden, dict):
                errors.append(f"query {query_id!r} forbidden_evidence must be an object")
                raw_forbidden = {}
            gold = set(map(str, raw_gold))
            forbidden = set(map(str, raw_forbidden.keys()))
            unknown_evidence = (gold | forbidden) - event_ids
            if unknown_evidence:
                errors.append(
                    f"query {query_id!r} references unknown evidence: {sorted(unknown_evidence)}"
                )
            if gold & forbidden:
                errors.append(f"query {query_id!r} has evidence marked both gold and forbidden")
            for evidence_id in gold | forbidden:
                if event_by_id.get(evidence_id, {}).get("type") != "message":
                    errors.append(f"query {query_id!r} evidence {evidence_id!r} is not a message")
            for reason in raw_forbidden.values():
                if reason not in FORBIDDEN_REASONS:
                    errors.append(f"query {query_id!r} has invalid forbidden reason {reason!r}")
            expected_decision = query.get(
                "expected_decision",
                "deny" if query.get("should_abstain", False) else "answer",
            )
            if expected_decision not in {"answer", "abstain", "deny", "clarify"}:
                errors.append(f"query {query_id!r} has invalid expected_decision")
            if not isinstance(query.get("should_abstain", False), bool):
                errors.append(f"query {query_id!r} should_abstain must be boolean")
            answer = query.get("answer", {})
            aliases = answer.get("aliases", []) if isinstance(answer, dict) else []
            required_items = answer.get("required_items", []) if isinstance(answer, dict) else []
            if not query.get("should_abstain", False) and not (aliases or required_items):
                errors.append(
                    f"answerable query {query_id!r} needs aliases or required answer items"
                )

        if check_policy and not errors:
            from .policy import PolicyOracle

            oracle = PolicyOracle(self)
            for event in self.events:
                if event.get("type") != "message":
                    continue
                space_id = str(event["space_id"])
                if oracle.history_policy(space_id, int(event["seq"])) != "public" and not oracle.is_member(
                    str(event["author_id"]), space_id, int(event["seq"])
                ):
                    errors.append(
                        f"message {event['id']!r} was authored outside an active membership"
                    )
            for query in self.queries:
                recipients = _recipients(query)
                for evidence_id in query.get("gold_evidence_ids", []):
                    if not oracle.audience_can_view(
                        str(evidence_id), recipients, int(query["after_seq"])
                    ):
                        errors.append(
                            f"query {query['id']!r} has policy-inaccessible gold evidence {evidence_id!r}"
                        )
                for evidence_id, reason in query.get("forbidden_evidence", {}).items():
                    if reason == "authorization" and oracle.audience_can_view(
                        str(evidence_id), recipients, int(query["after_seq"])
                    ):
                        errors.append(
                            f"query {query['id']!r} labels accessible evidence {evidence_id!r} as authorization-forbidden"
                        )
                    if reason == "deleted" and not oracle.is_deleted(
                        str(evidence_id), int(query["after_seq"])
                    ):
                        errors.append(
                            f"query {query['id']!r} labels live evidence {evidence_id!r} as deleted"
                        )

        if errors:
            raise DatasetValidationError("\n".join(f"- {error}" for error in errors))
        return errors


def _unique_ids(items: Iterable[dict[str, Any]], label: str, errors: list[str]) -> set[str]:
    ids: set[str] = set()
    for item in items:
        raw_id = item.get("id")
        if not isinstance(raw_id, str) or not raw_id:
            errors.append(f"{label} has a missing or invalid id")
            continue
        if raw_id in ids:
            errors.append(f"duplicate {label} id {raw_id!r}")
        ids.add(raw_id)
    return ids


def _recipients(query: dict[str, Any]) -> set[str]:
    return {str(query["requester_id"]), *(str(x) for x in query.get("audience_ids", []))}


def load_dataset(path: str | Path, *, validate: bool = True) -> BenchmarkDataset:
    with Path(path).open("r", encoding="utf-8") as handle:
        dataset = BenchmarkDataset(json.load(handle))
    if validate:
        dataset.validate()
    return dataset


def save_dataset(dataset: BenchmarkDataset | dict[str, Any], path: str | Path) -> None:
    raw = dataset.raw if isinstance(dataset, BenchmarkDataset) else dataset
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(raw, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
