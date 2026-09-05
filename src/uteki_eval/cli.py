from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .evaluator import ContractError, evaluate_metric_extraction


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="uteki-eval")
    subparsers = parser.add_subparsers(dest="command", required=True)
    evaluate = subparsers.add_parser("evaluate", help="score metric extraction predictions")
    evaluate.add_argument("--benchmark", required=True, type=Path)
    evaluate.add_argument("--predictions", required=True, type=Path)
    evaluate.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = evaluate_metric_extraction(args.benchmark, args.predictions)
    except (ContractError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0

