#!/usr/bin/env python3
"""Import an acquired filing into a new, verified candidate snapshot; no network."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from uteki.infrastructure.document_sources.snapshots import import_snapshot, verify_snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", type=Path, required=True, help="acquired original HTML bytes")
    parser.add_argument("--source-manifest", type=Path, required=True, help="expected filing identity and legacy hash")
    parser.add_argument("--asset", action="append", default=[], metavar="NAME=PATH", help="original attachment filename and acquired file")
    parser.add_argument("--output", type=Path, required=True, help="new directory; existing directories are never overwritten")
    parser.add_argument("--retrieved-at", required=True, help="actual retrieval time with timezone")
    parser.add_argument("--retrieval-method", required=True, choices=("https_download", "browser_file_download", "local_import"))
    parser.add_argument("--retrieval-url", required=True)
    parser.add_argument("--expected-paragraph-contract", help="optional historical legacy paragraph-contract SHA-256")
    args = parser.parse_args(argv)
    try:
        expected = json.loads(args.source_manifest.read_text(encoding="utf-8"))
        if args.expected_paragraph_contract:
            expected["expected_legacy_paragraph_contract_sha256"] = args.expected_paragraph_contract
        assets = {}
        for item in args.asset:
            name, separator, path = item.partition("=")
            if not separator or not name or not path or name in assets:
                raise ValueError("each --asset must use a unique NAME=PATH")
            assets[name] = Path(path).read_bytes()
        manifest = import_snapshot(
            args.html.read_bytes(), source_manifest=expected, assets=assets,
            output_dir=args.output, retrieved_at=args.retrieved_at,
            retrieval={"method": args.retrieval_method, "url": args.retrieval_url},
        )
        verify_snapshot(args.output)
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(f"Source preparation failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "verified_candidate", "output": str(args.output), "manifest": manifest}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
