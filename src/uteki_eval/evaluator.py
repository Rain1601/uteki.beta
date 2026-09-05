from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class ContractError(ValueError):
    """Raised when benchmark or prediction inputs violate the contract."""


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise ContractError(f"{path}:{line_number}: invalid JSON") from error
            if not isinstance(row, dict):
                raise ContractError(f"{path}:{line_number}: row must be an object")
            rows.append(row)
    return rows


def _index(rows: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        item_id = row.get("id")
        if not isinstance(item_id, str) or not item_id.strip():
            raise ContractError(f"{label}: every row requires a non-empty string id")
        if item_id in indexed:
            raise ContractError(f"{label}: duplicate id {item_id!r}")
        indexed[item_id] = row
    return indexed


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value).strip()).casefold()


def evaluate_metric_extraction(benchmark_path: Path, predictions_path: Path) -> dict[str, Any]:
    benchmark = _index(_load_jsonl(benchmark_path), "benchmark")
    predictions = _index(_load_jsonl(predictions_path), "predictions")
    unknown = sorted(set(predictions) - set(benchmark))
    if unknown:
        raise ContractError(f"predictions contain unknown ids: {', '.join(unknown)}")

    errors: list[dict[str, Any]] = []
    correct = 0
    answered = 0
    fields = ("value", "unit", "period")
    for item_id, item in benchmark.items():
        prediction = predictions.get(item_id)
        if prediction is None:
            errors.append({"id": item_id, "type": "missing_prediction"})
            continue
        answered += 1
        expected = item.get("expected")
        actual = prediction.get("predicted")
        if not isinstance(expected, dict) or not isinstance(actual, dict):
            errors.append({"id": item_id, "type": "malformed_prediction"})
            continue
        mismatched = [field for field in fields if _normalize(expected.get(field)) != _normalize(actual.get(field))]
        if mismatched:
            errors.append({"id": item_id, "type": "incorrect", "fields": mismatched})
        else:
            correct += 1

    total = len(benchmark)
    return {
        "task": "metric_extraction",
        "total": total,
        "answered": answered,
        "correct": correct,
        "accuracy": correct / total if total else 0.0,
        "coverage": answered / total if total else 0.0,
        "errors": errors,
    }

