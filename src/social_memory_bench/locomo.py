from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .dataset import BenchmarkDataset


def import_locomo(path: str | Path) -> list[BenchmarkDataset]:
    """Convert the official ``locomo10.json`` into compatibility scenarios.

    The resulting track preserves LoCoMo answers, categories, and evidence IDs.
    It intentionally remains dyadic and does not manufacture permission tests.
    """

    with Path(path).open("r", encoding="utf-8") as handle:
        samples = json.load(handle)
    if isinstance(samples, dict):
        samples = samples.get("data", samples.get("samples", []))
    if not isinstance(samples, list):
        raise ValueError("expected a LoCoMo list or a mapping containing data/samples")
    return [_convert_sample(sample, index) for index, sample in enumerate(samples)]


def _convert_sample(sample: dict[str, Any], index: int) -> BenchmarkDataset:
    conversation = sample.get("conversation", {})
    speaker_a = str(conversation.get("speaker_a", "Speaker A"))
    speaker_b = str(conversation.get("speaker_b", "Speaker B"))
    user_a = "u_speaker_a"
    user_b = "u_speaker_b"
    events: list[dict[str, Any]] = [
        {
            "seq": 1,
            "id": "join_a",
            "type": "membership",
            "space_id": "locomo_dm",
            "user_id": user_a,
            "action": "join",
        },
        {
            "seq": 2,
            "id": "join_b",
            "type": "membership",
            "space_id": "locomo_dm",
            "user_id": user_b,
            "action": "join",
        },
    ]
    evidence_id_map: dict[str, str] = {}
    session_keys = sorted(
        (
            key
            for key, value in conversation.items()
            if re.fullmatch(r"session_\d+", str(key)) and isinstance(value, list)
        ),
        key=lambda key: int(str(key).split("_")[-1]),
    )
    for session_key in session_keys:
        for turn in conversation[session_key]:
            original_id = str(turn.get("dia_id", f"turn_{len(events)}"))
            event_id = _safe_id(original_id, fallback=f"turn_{len(events)}")
            if event_id in evidence_id_map.values():
                event_id = f"{event_id}_{len(events)}"
            evidence_id_map[original_id] = event_id
            speaker = str(turn.get("speaker", speaker_a))
            if speaker == speaker_a:
                author_id = user_a
            elif speaker == speaker_b:
                author_id = user_b
            else:
                raise ValueError(f"unexpected LoCoMo speaker {speaker!r} in {session_key}")
            text = turn.get("text")
            if not isinstance(text, str) or not text.strip():
                text = turn.get("blip_caption", "")
            if text is None:
                text = ""
            events.append(
                {
                    "seq": len(events) + 1,
                    "id": event_id,
                    "type": "message",
                    "space_id": "locomo_dm",
                    "author_id": author_id,
                    "modality": "image" if turn.get("img_url") else "text",
                    "observed_text": str(text),
                    "source_session": session_key,
                    "source_timestamp": conversation.get(f"{session_key}_date_time"),
                }
            )
    final_seq = len(events)
    queries: list[dict[str, Any]] = []
    for qa_index, qa in enumerate(sample.get("qa", [])):
        answer = qa.get("answer", "")
        if isinstance(answer, list):
            aliases = [str(item) for item in answer]
        elif answer is None:
            aliases = []
        else:
            aliases = [str(answer)] if str(answer).strip() else []
        raw_evidence = [str(item) for item in qa.get("evidence", [])]
        unmapped = sorted(set(raw_evidence) - evidence_id_map.keys())
        if unmapped:
            raise ValueError(f"LoCoMo QA {qa_index} has unmapped evidence IDs: {unmapped}")
        evidence = [evidence_id_map[item] for item in raw_evidence]
        category = str(qa.get("category", "unknown"))
        should_abstain = not aliases
        queries.append(
            {
                "id": f"q_{qa_index:04d}",
                "after_seq": final_seq,
                "requester_id": user_a,
                "audience_ids": [user_a],
                "active_space_id": "locomo_dm",
                "purpose": "compatibility_evaluation",
                "task": f"locomo_{category}",
                "question": str(qa.get("question", "")),
                "answer": {"aliases": aliases},
                "gold_evidence_ids": evidence,
                "forbidden_evidence": {},
                "should_abstain": should_abstain,
                "expected_decision": "abstain" if should_abstain else "answer",
                "tags": ["locomo", "compatibility"],
            }
        )
    raw = {
        "benchmark_version": "0.2",
        "scenario_id": f"locomo-{_safe_id(str(sample.get('sample_id', index)))}",
        "description": "LoCoMo compatibility import; no synthetic access-control labels added.",
        "entities": [
            {"id": user_a, "kind": "user", "display_name": speaker_a, "aliases": []},
            {"id": user_b, "kind": "user", "display_name": speaker_b, "aliases": []},
        ],
        "spaces": [
            {
                "id": "locomo_dm",
                "kind": "dm",
                "display_name": f"{speaker_a} ↔ {speaker_b}",
                "history_policy": "retain_seen",
            }
        ],
        "events": events,
        "queries": queries,
        "metadata": {
            "source": "LoCoMo",
            "source_sample_id": sample.get("sample_id", index),
            "source_url": "https://github.com/snap-research/locomo",
        },
    }
    dataset = BenchmarkDataset(raw)
    dataset.validate()
    return dataset


def _safe_id(value: str, *, fallback: str = "item") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")
    return cleaned or fallback
