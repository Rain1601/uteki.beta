from __future__ import annotations

import argparse
from pathlib import Path

from uteki.infrastructure.research_data.artifacts import build_research_data_artifacts


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Alphabet research-data candidate bundle")
    parser.add_argument("--generated-at", required=True, help="Pinned ISO-8601 generation time")
    args = parser.parse_args()
    manifest = build_research_data_artifacts(
        ROOT / "benchmarks/alphabet_2025_business_map/v0.3-candidate",
        ROOT / "data/source_documents/alphabet_2025_10k",
        ROOT / "data/research_data/alphabet_2025_10k/v0.2-candidate",
        generated_at=args.generated_at,
    )
    print(
        f"built {manifest['bundle_id']} with {manifest['counts']['claims']} claims and "
        f"{manifest['counts']['evidence_links']} evidence links"
    )


if __name__ == "__main__":
    main()
