"""JSON command-line adapter shared by human and Agent clients."""
import argparse
import json
from pathlib import Path
import sys

import duckdb

from .query_dataset import build_dataset
from .query_service import QueryDataPort


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="write a new JSON artifact; existing files are never overwritten")
    commands = parser.add_subparsers(dest="tool", required=True)
    build = commands.add_parser("build")
    build.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[4])
    build.add_argument("--destination", type=Path, required=True)
    build.add_argument("--spec", type=Path, required=True, help="explicit hash-pinned build specification")
    for name in ("schema", "discover", "query", "evidence", "read"):
        tool = commands.add_parser(name)
        tool.add_argument("--dataset", type=Path, required=True)
        if name == "schema":
            tool.add_argument("--metric", action="append", default=[])
        elif name == "query":
            tool.add_argument("--request", type=Path, required=True)
        else:
            tool.add_argument("--as-of", required=True)
            tool.add_argument("--include-candidates", action="store_true")
            if name == "evidence":
                tool.add_argument("--id", action="append", required=True)
            elif name == "read":
                tool.add_argument("--source", required=True)
                tool.add_argument("--block", required=True)
    args = parser.parse_args(argv)
    try:
        if args.out and args.out.exists():
            raise FileExistsError("output artifact exists")
        if args.tool == "build":
            result = build_dataset(args.repo, args.destination, spec=args.spec)
        else:
            with QueryDataPort(args.dataset) as port:
                if args.tool == "schema":
                    result = port.get_schema(args.metric)
                elif args.tool == "discover":
                    result = port.discover_data(knowledge_cutoff=args.as_of, include_candidates=args.include_candidates)
                elif args.tool == "query":
                    result = port.query_data(json.loads(args.request.read_text()))
                elif args.tool == "evidence":
                    result = port.get_evidence(args.id, snapshot_id=port.snapshot_id, knowledge_cutoff=args.as_of,
                                               include_candidates=args.include_candidates)
                else:
                    result = port.read_context(source_snapshot_id=args.source, block_id=args.block, snapshot_id=port.snapshot_id,
                                               knowledge_cutoff=args.as_of, include_candidates=args.include_candidates)
        output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x") as stream:
                stream.write(output)
        else:
            print(output, end="")
        return 0
    except (ValueError, KeyError, OSError, RuntimeError, duckdb.Error) as error:
        print(json.dumps({"status": "failed", "error_type": type(error).__name__, "message": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
