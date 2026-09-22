"""Export existing data contracts for inspection; does not create a query service.

Uses Pydantic from the project's analysis environment. Dataclass JSON schemas
describe field shapes; Python post-init and cross-record checks remain required.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from pydantic import TypeAdapter

from uteki.domain.research_data.models import EvidenceBundle, ResearchDataQuery, ResearchDataRequest
from uteki.infrastructure.research_data.extraction_prompts import Extraction

ROOT = Path(__file__).resolve().parents[1]
MODELS = "src/uteki/domain/research_data/models.py"
EXTRACTION = "src/uteki/infrastructure/research_data/extraction_prompts.py"


def export(output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for name, model, source in (
        ("extraction", Extraction, EXTRACTION),
        ("research-data-query", ResearchDataQuery, MODELS),
        ("evidence-bundle", EvidenceBundle, MODELS),
        ("research-data-request", ResearchDataRequest, MODELS),
    ):
        schema = TypeAdapter(model).json_schema()
        raw = (json.dumps(schema, ensure_ascii=False, indent=2) + "\n").encode()
        filename = f"{name}.schema.json"
        (output_dir / filename).write_bytes(raw)
        entries.append({
            "name": name,
            "model": model.__name__,
            "schema_file": filename,
            "schema_sha256": hashlib.sha256(raw).hexdigest(),
            "source_file": source,
            "source_sha256": hashlib.sha256((ROOT / source).read_bytes()).hexdigest(),
            "scope": "experimental prompt output" if model is Extraction else "existing handoff contract",
        })
    catalog = {
        "catalog_version": "schema-inventory-v0.1",
        "json_schema_dialect": "https://json-schema.org/draft/2020-12/schema",
        "entries": entries,
        "code_defined_contracts_without_formal_json_schema": [
            {"name": "financial-records-v0.2", "source_file": "src/uteki/infrastructure/research_data/financial_records.py"},
            {"name": "transcript-records-v0.2", "source_file": "src/uteki/infrastructure/research_data/transcript_records.py"},
        ],
        "limits": [
            "Field-shape export only; not a physical SQL schema or dataset coverage catalog.",
            "Dataclass post-init constraints and evidence/source integrity checks are not encoded in these schemas.",
            "Existing MetricPoint.value is an integer; experimental Extraction.value is a nullable string.",
            "Schema availability does not imply dataset availability, semantic correctness or publication approval.",
            "No get_schema endpoint, SQL executor, OCR or web-search router is created by this export.",
        ],
    }
    (output_dir / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n")
    return catalog


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs/schemas/current")
    args = parser.parse_args()
    catalog = export(args.output_dir)
    print(json.dumps({"output_dir": str(args.output_dir.resolve()), "schemas": len(catalog["entries"])}, ensure_ascii=False))
