import json
import tempfile
import unittest
from pathlib import Path

from mem_ledger_bench.locomo import import_locomo


class LoCoMoImportTest(unittest.TestCase):
    def _write(self, value):
        directory = tempfile.TemporaryDirectory()
        path = Path(directory.name) / "locomo.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return directory, path

    def test_import_preserves_evidence_and_uses_image_caption(self) -> None:
        sample = [
            {
                "sample_id": "sample-1",
                "conversation": {
                    "speaker_a": "A",
                    "speaker_b": "B",
                    "session_1_date_time": "2026-01-01T00:00:00Z",
                    "session_1": [
                        {"speaker": "A", "dia_id": "d1", "text": "The code is Kestrel."},
                        {
                            "speaker": "B",
                            "dia_id": "d2",
                            "text": "",
                            "img_url": "https://example.invalid/image",
                            "blip_caption": "a blue bicycle",
                        },
                    ],
                },
                "qa": [
                    {
                        "question": "What is the code?",
                        "answer": "Kestrel",
                        "category": 1,
                        "evidence": ["d1"],
                    }
                ],
            }
        ]
        directory, path = self._write(sample)
        try:
            dataset = import_locomo(path)[0]
        finally:
            directory.cleanup()
        self.assertEqual(["d1"], dataset.queries[0]["gold_evidence_ids"])
        self.assertEqual("a blue bicycle", dataset.event_by_id()["d2"]["observed_text"])

    def test_unmapped_evidence_fails_loudly(self) -> None:
        sample = [
            {
                "conversation": {
                    "speaker_a": "A",
                    "speaker_b": "B",
                    "session_1": [{"speaker": "A", "dia_id": "d1", "text": "hello"}],
                },
                "qa": [{"question": "?", "answer": "x", "evidence": ["missing"]}],
            }
        ]
        directory, path = self._write(sample)
        try:
            with self.assertRaisesRegex(ValueError, "unmapped evidence"):
                import_locomo(path)
        finally:
            directory.cleanup()


if __name__ == "__main__":
    unittest.main()

