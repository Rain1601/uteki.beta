from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from uteki_eval import ContractError, evaluate_metric_extraction


class EvaluatorTests(unittest.TestCase):
    def _write(self, directory: Path, name: str, rows: list[dict]) -> Path:
        path = directory / name
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        return path

    def test_scores_correct_incorrect_and_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            benchmark = self._write(directory, "benchmark.jsonl", [
                {"id": "a", "expected": {"value": "10", "unit": "USD", "period": "Q1"}},
                {"id": "b", "expected": {"value": "20", "unit": "USD", "period": "Q1"}},
                {"id": "c", "expected": {"value": "30", "unit": "USD", "period": "Q1"}},
            ])
            predictions = self._write(directory, "predictions.jsonl", [
                {"id": "a", "predicted": {"value": " 10 ", "unit": "usd", "period": "q1"}},
                {"id": "b", "predicted": {"value": "21", "unit": "USD", "period": "Q1"}},
            ])
            result = evaluate_metric_extraction(benchmark, predictions)
            self.assertEqual(result["correct"], 1)
            self.assertEqual(result["answered"], 2)
            self.assertAlmostEqual(result["accuracy"], 1 / 3)
            self.assertAlmostEqual(result["coverage"], 2 / 3)
            self.assertEqual([error["type"] for error in result["errors"]], ["incorrect", "missing_prediction"])

    def test_rejects_unknown_prediction_id(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            benchmark = self._write(directory, "benchmark.jsonl", [{"id": "a", "expected": {}}])
            predictions = self._write(directory, "predictions.jsonl", [{"id": "x", "predicted": {}}])
            with self.assertRaises(ContractError):
                evaluate_metric_extraction(benchmark, predictions)

    def test_rejects_duplicate_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            benchmark = self._write(directory, "benchmark.jsonl", [{"id": "a"}, {"id": "a"}])
            predictions = self._write(directory, "predictions.jsonl", [])
            with self.assertRaises(ContractError):
                evaluate_metric_extraction(benchmark, predictions)


if __name__ == "__main__":
    unittest.main()
