"""Run the rule baseline from source only. Evaluate its artifact separately."""
from datetime import datetime, timezone
from pathlib import Path
import json

from uteki.infrastructure.research_data.cloud_spike import CloudReader, digest, encoded, extract, simulate

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = ROOT / "data/source_documents/alphabet_2025_10k"
    started = datetime.now(timezone.utc).isoformat()
    snapshot = extract(source)
    reader = CloudReader(snapshot, as_of=snapshot["available_at"])
    trace = simulate(reader)
    code = ROOT / "src/uteki/infrastructure/research_data/cloud_spike.py"
    run = {"started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
           "method": "deterministic_rule_baseline", "model": None, "prompt": None,
           "extractor_version": snapshot["extractor_version"], "code_sha256": digest(code.read_bytes()),
           "snapshot_id": snapshot["snapshot_id"], "source_sha256": snapshot["source_sha256"],
           "index_id": snapshot["index_id"], "selected_node_ids": snapshot["selected_node_ids"],
           "status": "candidate", "limitations": ["single-filing rules", "not an LLM capability test",
           "reference is source-reviewed by Codex and pending human review", "no general semantic search"]}
    run_id = "run-" + digest(encoded(run))[:16]
    out = ROOT / "data/research_data/google_cloud_spike" / run_id
    out.mkdir(parents=True, exist_ok=False)
    for name, value in (("snapshot.json", snapshot), ("run.json", run), ("trace.json", trace)):
        (out / name).write_bytes(encoded(value))
    print(json.dumps({"run_id": run_id, "path": str(out), "facts": len(snapshot["facts"]),
                      "tool_calls": len(trace)}, indent=2))


if __name__ == "__main__":
    main()
