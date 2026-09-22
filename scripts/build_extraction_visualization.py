"""Build a self-contained read-only view from the frozen extraction experiment."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments/research_data_quality"


def build(destination: Path) -> None:
    payload: dict = {"cases": {}, "runs": {}}
    hashes = {}

    def read(path: Path) -> dict:
        content = path.read_bytes()
        hashes[str(path.relative_to(ROOT))] = hashlib.sha256(content).hexdigest()
        return json.loads(content)

    for case in ("F1", "T1", "T2"):
        packet = read(EXPERIMENT / f"2026-09-22-prompt-protocol/cases/{case}.json")["packet"]
        blocks = {}
        for block in packet["blocks"]:
            blocks[block["block_id"]] = {
                **block,
                "document_id": block.get("document_id", packet.get("document_id")),
            }
        payload["cases"][case] = {
            "index_id": packet.get("index_id", packet["blocks"][0].get("index_id")),
            "blocks": blocks,
        }
        for arm in ("control", "claude_adapted"):
            for repeat in (1, 2):
                key = f"{case}-{arm}-{repeat}"
                output = read(EXPERIMENT / f"2026-09-22-prompt-run-01/{key}/output.json")
                for record in output["records"]:
                    for citation in record["evidence"] + record["qualifiers"]:
                        if citation["quote"] not in blocks[citation["block_id"]]["text"]:
                            raise ValueError(f"Unverifiable quote in {key}")
                    for ref in record["question_refs"]:
                        if ref not in blocks:
                            raise ValueError(f"Unknown question in {key}")
                payload["runs"][key] = output
    template = ROOT / "scripts/templates/extraction-results.html"
    # JSON only is embedded. Literal fragment markup lives in the template.
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    fragment = template.read_text().replace("__EXTRACTION_DATA__", serialized)
    if len(fragment.encode()) >= 1_000_000:
        raise ValueError("Visualization exceeds the fragment size limit")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(fragment)
    manifest = {
        "source_hashes": hashes,
        "template_sha256": hashlib.sha256(template.read_bytes()).hexdigest(),
        "fragment_sha256": hashlib.sha256(fragment.encode()).hexdigest(),
        "runs": len(payload["runs"]),
        "record_occurrences": sum(len(r["records"]) for r in payload["runs"].values()),
        "default_record_count": sum(len(payload["runs"][f"{c}-claude_adapted-1"]["records"]) for c in ("F1", "T1", "T2")),
        "source_quotes_verified": True,
        "status": "candidate; presentation only; no source mutation",
    }
    destination.with_suffix(".manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"path": str(destination), "bytes": len(fragment.encode()), **{k:v for k,v in manifest.items() if k not in ("source_hashes",)}}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    build(parser.parse_args().destination)
