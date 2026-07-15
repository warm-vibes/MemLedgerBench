import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from mem_ledger_bench.cli import main
from mem_ledger_bench.suite import aggregate_world_results


class SuiteTest(unittest.TestCase):
    def test_world_level_bootstrap(self) -> None:
        results = [
            {
                "dataset_metadata": {"scale": "tiny", "seed": index},
                "summary": {
                    "safe_memory_score": score,
                    "task_utility": score / 100,
                    "evidence_f1": 0.5,
                    "safety": 1.0,
                    "deployment_gate_pass": True,
                },
            }
            for index, score in enumerate((50.0, 70.0))
        ]
        aggregate = aggregate_world_results(results, bootstrap_samples=100, seed=1)
        self.assertEqual(2, aggregate["worlds"])
        self.assertEqual(60.0, aggregate["overall"]["safe_memory_score"]["mean"])
        self.assertTrue(aggregate["deployment_gate_pass"])

    def test_overall_bootstrap_clusters_scale_variants_by_seed(self) -> None:
        results = []
        for seed, scores in ((7, (40.0, 60.0)), (11, (80.0, 100.0))):
            for scale, score in zip(("tiny", "stress"), scores):
                results.append(
                    {
                        "dataset_metadata": {"scale": scale, "seed": seed},
                        "summary": {
                            "safe_memory_score": score,
                            "task_utility": score / 100,
                            "evidence_f1": 0.5,
                            "safety": 1.0,
                            "deployment_gate_pass": True,
                        },
                    }
                )
        aggregate = aggregate_world_results(results, bootstrap_samples=100, seed=1)
        self.assertEqual(2, aggregate["independent_seed_clusters"])
        self.assertEqual(70.0, aggregate["overall"]["safe_memory_score"]["mean"])

    def test_suite_cli_runs_a_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "matrix.json"
            output = root / "suite.json"
            config.write_text(
                json.dumps({"seeds": [7], "scales": ["tiny"], "repetitions": 1}),
                encoding="utf-8",
            )
            with redirect_stdout(io.StringIO()):
                exit_code = main(
                    [
                        "suite",
                        "--config",
                        str(config),
                        "--adapter",
                        "bm25-policy",
                        "--out",
                        str(output),
                    ]
                )
            self.assertEqual(0, exit_code)
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(1, result["aggregate"]["worlds"])


if __name__ == "__main__":
    unittest.main()
