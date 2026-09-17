"""Compare a completed source-only run with a separate candidate reference."""
import argparse
import json
from pathlib import Path

from uteki.infrastructure.research_data.cloud_spike import digest, encoded

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    reference_path = ROOT / "benchmarks/google_cloud_spike/v0.1-candidate/reference.json"
    reference = json.loads(reference_path.read_text())
    snapshot_path = args.run_dir / "snapshot.json"
    snapshot = json.loads(snapshot_path.read_text())
    run = json.loads((args.run_dir / "run.json").read_text())
    expected = {("offerings", None): (reference["offerings"], None)}
    expected.update({(metric, period): (value, reference["unit"])
                     for metric, points in reference["metrics"].items() for period, value in points.items()})
    actual, errors = {}, []
    for fact in snapshot["facts"]:
        if fact["subject_id"] != "google-cloud":
            errors.append({"kind": "subject_mismatch", "fact_id": fact["fact_id"]})
        key = (fact["predicate"], fact["period"])
        if key in actual:
            errors.append({"kind": "duplicate", "key": key})
        actual[key] = (fact["value"], fact["unit"])
    for key in expected.keys() | actual.keys():
        if key not in actual:
            errors.append({"kind": "missing", "key": key})
        elif key not in expected:
            errors.append({"kind": "unexpected", "key": key})
        elif actual[key] != expected[key]:
            errors.append({"kind": "mismatch", "key": key, "expected": expected[key], "actual": actual[key]})
    if snapshot["source_snapshot_id"] != reference["source_snapshot_id"]:
        errors.append({"kind": "source_mismatch"})
    report = {"status": "candidate_reference_comparison", "human_review": "pending",
              "snapshot_id": snapshot["snapshot_id"], "snapshot_sha256": digest(snapshot_path.read_bytes()),
              "reference_sha256": digest(reference_path.read_bytes()), "expected_records": len(expected),
              "actual_records": len(snapshot["facts"]), "errors": errors,
              "limitations": ("One LLM run; candidate reference is not independent gold. No generalization claim."
                              if run["method"] == "llm_extraction" else
                              "Same-source rule development; no LLM/generalization/completeness claim.")}
    out = ROOT / "experiments/google_cloud_spike" / args.run_dir.name
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / "evaluation.json"
    content = encoded(report)
    if report_path.exists() and report_path.read_bytes() != content:
        raise FileExistsError("evaluation already exists with different inputs")
    report_path.write_bytes(content)
    print(content.decode())
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
