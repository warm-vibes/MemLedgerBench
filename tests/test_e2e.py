import unittest
import sys
from pathlib import Path

from social_memory_bench.adapters import (
    JsonlCommandAdapter,
    LexicalAdapter,
    MemoryAdapter,
    MemoryResponse,
)
from social_memory_bench.generator import generate_dataset
from social_memory_bench.policy import PolicyOracle
from social_memory_bench.runner import _with_derived_forbidden, run_benchmark


class EndToEndTest(unittest.TestCase):
    def test_adapter_is_closed_when_reset_fails(self) -> None:
        class ResetFailAdapter(MemoryAdapter):
            name = "reset-fail"

            def __init__(self) -> None:
                self.closed = False

            def reset(self, scenario):
                raise RuntimeError("reset failed")

            def ingest(self, event):
                raise AssertionError("unreachable")

            def answer(self, query):
                raise AssertionError("unreachable")

            def close(self):
                self.closed = True

        adapter = ResetFailAdapter()
        with self.assertRaisesRegex(RuntimeError, "reset failed"):
            run_benchmark(generate_dataset(scale="tiny", seed=7), adapter)
        self.assertTrue(adapter.closed)

    def test_policy_filter_reduces_critical_leakage(self) -> None:
        dataset = generate_dataset(scale="tiny", seed=7)
        safe = run_benchmark(dataset, LexicalAdapter(top_k=3, policy_aware=True))
        unsafe = run_benchmark(dataset, LexicalAdapter(top_k=3, policy_aware=False))
        self.assertLessEqual(
            safe["summary"]["critical_policy_violations"],
            unsafe["summary"]["critical_policy_violations"],
        )
        self.assertGreater(safe["summary"]["evidence_recall"], 0.0)
        edited = next(row for row in safe["responses"] if row["query_id"] == "q_message_edit")
        self.assertEqual(1.0, edited["answer_hit"])

    def test_small_generation_is_reproducible(self) -> None:
        first = generate_dataset(scale="small", seed=11)
        second = generate_dataset(scale="small", seed=11)
        self.assertEqual(first.raw, second.raw)
        self.assertEqual(250, first.raw["metadata"]["config"]["distractors"])
        tiny = generate_dataset(scale="tiny", seed=11)
        small_query = next(query for query in first.queries if query["id"] == "q_direct_codename")
        tiny_query = next(query for query in tiny.queries if query["id"] == "q_direct_codename")
        self.assertGreater(small_query["after_seq"], tiny_query["after_seq"])

    def test_gold_and_generator_metadata_are_not_exposed(self) -> None:
        class CaptureAdapter(MemoryAdapter):
            name = "capture"

            def __init__(self) -> None:
                self.scenario = {}
                self.events = []
                self.queries = []

            def reset(self, scenario):
                self.scenario = scenario
                self.assert_no_gold_surface = not any(
                    key in scenario for key in ("raw", "queries", "events")
                )

            def ingest(self, event):
                self.events.append(event)

            def answer(self, query):
                self.queries.append(query)
                return MemoryResponse(answer="", decision="abstain")

        adapter = CaptureAdapter()
        dataset = generate_dataset(scale="tiny", seed=7)
        run_benchmark(dataset, adapter, perform_recovery=False)
        self.assertTrue(adapter.assert_no_gold_surface)
        self.assertNotIn("seed", adapter.scenario.get("metadata", {}))
        self.assertTrue(all("reference_text" not in event for event in adapter.events))
        self.assertTrue(all("answer" not in query for query in adapter.queries))
        self.assertTrue(all("gold_evidence_ids" not in query for query in adapter.queries))
        self.assertTrue(all("task" not in query and "tags" not in query for query in adapter.queries))
        gold_ids = {str(query["id"]) for query in dataset.queries}
        wire_ids = [str(query["id"]) for query in adapter.queries]
        self.assertTrue(all(wire_id not in gold_ids for wire_id in wire_ids))
        self.assertTrue(all(wire_id.startswith("q_") for wire_id in wire_ids))
        self.assertEqual(len(dataset.queries), len(set(wire_ids)))

    def test_jsonl_product_protocol(self) -> None:
        script = Path(__file__).resolve().parents[1] / "examples" / "unsafe_jsonl_adapter.py"
        adapter = JsonlCommandAdapter([sys.executable, str(script)])
        result = run_benchmark(generate_dataset(scale="tiny", seed=7), adapter)
        self.assertEqual("jsonl-command", result["adapter"])
        self.assertEqual(16, result["summary"]["queries"])
        self.assertGreater(result["system_stats"]["indexed_messages"], 0)

    def test_jsonl_timeout_and_top_k_validation(self) -> None:
        adapter = JsonlCommandAdapter(
            [sys.executable, "-c", "import time; time.sleep(5)"],
            timeout_seconds=0.05,
        )
        try:
            with self.assertRaises(TimeoutError):
                adapter.reset({})
        finally:
            adapter.close()
        with self.assertRaises(ValueError):
            LexicalAdapter(top_k=0)

    def test_evaluator_derives_unlisted_policy_violations(self) -> None:
        dataset = generate_dataset(scale="tiny", seed=7)
        queries = {query["id"]: query for query in dataset.queries}
        enriched = _with_derived_forbidden(
            queries["q_voice_asr"],
            {
                "retrieved_event_ids": [
                    "m_private_venue",
                    "m_launch_after_leave",
                    "fabricated-id",
                ]
            },
            PolicyOracle(dataset),
            dataset,
        )
        self.assertEqual("authorization", enriched["forbidden_evidence"]["m_private_venue"])
        self.assertEqual("future", enriched["forbidden_evidence"]["m_launch_after_leave"])
        self.assertEqual("unknown_evidence", enriched["forbidden_evidence"]["fabricated-id"])

        after_recovery = dict(queries["q_after_recovery"])
        after_recovery["forbidden_evidence"] = {}
        enriched = _with_derived_forbidden(
            after_recovery,
            {"retrieved_event_ids": ["m_temporary_code"]},
            PolicyOracle(dataset),
            dataset,
        )
        self.assertEqual("deleted", enriched["forbidden_evidence"]["m_temporary_code"])


if __name__ == "__main__":
    unittest.main()
