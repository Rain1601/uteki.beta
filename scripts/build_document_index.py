from __future__ import annotations

import argparse
from pathlib import Path

from uteki.infrastructure.document_sources.index_artifacts import build_index_artifacts


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a deterministic Uteki SEC Document Index candidate.")
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=ROOT / "data/source_documents/alphabet_2025_10k",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data/source_documents/alphabet_2025_10k/indexes/v0.1-candidate",
    )
    args = parser.parse_args()
    manifest = build_index_artifacts(args.snapshot, args.output)
    counts = manifest["counts"]
    print(
        f"Built {manifest['index_id']}: {counts['parts']} Parts, {counts['items']} Items, "
        f"{counts['blocks']} Blocks, {counts['diagnostics']} diagnostics"
    )


if __name__ == "__main__":
    main()
