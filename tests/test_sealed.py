import json
import unittest

from mem_ledger_bench import runner as runner_mod
from mem_ledger_bench.adapters import MemoryAdapter, MemoryResponse, ReferenceControlAdapter
from mem_ledger_bench.generator import generate_dataset, seal_dataset
from mem_ledger_bench.runner import run_benchmark


class SealTest(unittest.TestCase):
    def test_seal_is_opaque(self) -> None:
        sealed = seal_dataset(generate_dataset(scale="tiny", seed=7), nonce="n-123")
        blob = json.dumps(sealed.raw)
        for semantic in (
            "m_prompt_injection",
            "m_launch_codename",
            "group_launch",
            "u_omar",
            "q_memory_poisoning",
            "social-lifecycle",
        ):
            self.assertNotIn(semantic, blob)
        self.assertTrue(sealed.scenario_id.startswith("sealed-"))
        self.assertTrue(sealed.raw["metadata"]["sealed"])

    def test_seal_is_score_preserving(self) -> None:
        public = generate_dataset(scale="tiny", seed=7)
        sealed = seal_dataset(public, nonce="n-123")
        a = run_benchmark(public, ReferenceControlAdapter(top_k=5), repetitions=3)["summary"]
        b = run_benchmark(sealed, ReferenceControlAdapter(top_k=5), repetitions=3)["summary"]
        for key in (
            "safe_memory_score",
            "task_utility",
            "evidence_f1",
            "safety",
            "critical_policy_violations",
            "deployment_gate_pass",
        ):
            self.assertEqual(a[key], b[key])

    def test_seal_is_deterministic_in_nonce(self) -> None:
        public = generate_dataset(scale="tiny", seed=7)
        self.assertEqual(seal_dataset(public, "same").raw, seal_dataset(public, "same").raw)
        self.assertNotEqual(
            seal_dataset(public, "same").scenario_id,
            seal_dataset(public, "other").scenario_id,
        )


class OrderingTest(unittest.TestCase):
    def test_ground_truth_is_built_after_every_answer(self) -> None:
        state = {"oracle_built": False}
        real_oracle = runner_mod.PolicyOracle

        class SpyOracle(real_oracle):  # type: ignore[misc, valid-type]
            def __init__(self, dataset):
                state["oracle_built"] = True
                super().__init__(dataset)

        test = self

        class GuardAdapter(MemoryAdapter):
            name = "guard"

            def reset(self, scenario):
                self.events = []

            def ingest(self, event):
                self.events.append(event)

            def answer(self, query):
                test.assertFalse(
                    state["oracle_built"], "ground truth was built before answers were locked"
                )
                return MemoryResponse(answer="", decision="abstain")

        runner_mod.PolicyOracle = SpyOracle
        try:
            run_benchmark(generate_dataset(scale="tiny", seed=7), GuardAdapter(), repetitions=2)
        finally:
            runner_mod.PolicyOracle = real_oracle
        self.assertTrue(state["oracle_built"])


if __name__ == "__main__":
    unittest.main()
