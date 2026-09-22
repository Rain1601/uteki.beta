from __future__ import annotations

import argparse
from pathlib import Path

from uteki.infrastructure.research_data.artifacts import build_research_data_artifacts


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Alphabet research-data candidate bundle")
    parser.add_argument("--adapter", required=True, choices=["alphabet-fy2025-business-map-v1"])
    parser.add_argument("--benchmark", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--generated-at", required=True, help="Pinned ISO-8601 generation time")
    args = parser.parse_args()
    manifest = build_research_data_artifacts(
        args.benchmark,
        args.source,
        args.destination,
        adapter_id=args.adapter,
        generated_at=args.generated_at,
    )
    print(
        f"built {manifest['bundle_id']} with {manifest['counts']['claims']} claims and "
        f"{manifest['counts']['evidence_links']} evidence links"
    )


if __name__ == "__main__":
    main()
