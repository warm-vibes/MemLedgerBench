import copy
import unittest

from social_memory_bench.dataset import BenchmarkDataset, DatasetValidationError
from social_memory_bench.generator import generate_dataset


class DatasetValidationTest(unittest.TestCase):
    def test_event_sequences_start_at_one(self) -> None:
        raw = copy.deepcopy(generate_dataset(scale="tiny", seed=7).raw)
        raw["events"][0]["seq"] = 0
        with self.assertRaisesRegex(DatasetValidationError, "at least 1"):
            BenchmarkDataset(raw).validate()

    def test_query_must_target_a_real_checkpoint(self) -> None:
        raw = copy.deepcopy(generate_dataset(scale="tiny", seed=7).raw)
        for event in raw["events"]:
            if event["seq"] >= 5:
                event["seq"] += 1
        for query in raw["queries"]:
            if query["after_seq"] >= 5:
                query["after_seq"] += 1
        raw["queries"][0]["after_seq"] = 5
        with self.assertRaisesRegex(DatasetValidationError, "does not match an event checkpoint"):
            BenchmarkDataset(raw).validate()

    def test_forbidden_evidence_must_be_an_object(self) -> None:
        raw = copy.deepcopy(generate_dataset(scale="tiny", seed=7).raw)
        raw["queries"][0]["forbidden_evidence"] = []
        with self.assertRaisesRegex(DatasetValidationError, "forbidden_evidence must be an object"):
            BenchmarkDataset(raw).validate()


if __name__ == "__main__":
    unittest.main()
