"""Inspect local inputs without network access, model calls or archive writes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.review_workbench.workspace_check import format_report, inspect_workspace


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="Workspace to inspect; never modified")
    parser.add_argument("--json", action="store_true", help="Machine-readable diagnostics")
    args = parser.parse_args(argv)
    report = inspect_workspace(args.root)
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else format_report(report))
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
