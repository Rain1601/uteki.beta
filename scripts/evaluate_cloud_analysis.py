"""Evaluate saved actions, evidence coverage and arithmetic without model calls."""
import argparse
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from uteki.agents.cloud_analysis import AnalysisTools, validate_answer
from uteki.agents.cloud_recovery import RecoveryTools
from uteki.infrastructure.research_data.cloud_spike import digest, encoded


def evaluate(folder):
    def read(name):
        return json.loads((folder / name).read_text())
    run, snapshot, answer = read("run.json"), read("input_snapshot.json"), read("answer.json")
    trace, comparisons, rounds = read("trace.json"), read("comparisons.json"), read("rounds.json")
    errors = []
    if digest((folder / "input_snapshot.json").read_bytes()) != run["snapshot_sha256"]:
        errors.append("input_snapshot_hash_mismatch")
    gap = bool(run.get('fixture'))
    root = folder.resolve().parents[2]
    tools = (RecoveryTools(snapshot, run['as_of'], root / 'data/source_documents/alphabet_2025_10k') if gap else
             AnalysisTools(snapshot, run["as_of"]))
    for t in trace:
        if tools.call(t["tool"], t["arguments"]) != t["response"]:
            errors.append(f"tool_response_mismatch:{t['step']}")
    try:
        validate_answer(answer, tools)
    except (ValueError, KeyError, TypeError) as exc:
        errors.append(f"answer_invalid:{exc}")
    actions = [c for r in rounds for c in r["action"].get("calls", [])]
    if actions != [{"tool": t["tool"], "arguments": t["arguments"]} for t in trace]:
        errors.append("model_action_trace_mismatch")
    if rounds[-1]["action"].get("answer") != answer:
        errors.append("final_answer_mismatch")
    if comparisons != tools.comparisons:
        errors.append("comparison_artifact_mismatch")
    resolved = read('resolved_snapshot.json') if gap else snapshot
    if gap and resolved != tools.resolved_snapshot():
        errors.append('recovered_overlay_mismatch')
    facts = {f["fact_id"]: f for f in resolved["facts"]}
    for cid, c in comparisons.items():
        a, b = facts[c["start_fact_id"]], facts[c["end_fact_id"]]
        expected = Decimal(b["value"]) - Decimal(a["value"])
        rate = str((expected / Decimal(a["value"]) * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) if a["value"] > 0 else None
        if c["delta"] != expected or c["growth_percent"] != rate:
            errors.append(f"arithmetic_mismatch:{cid}")
    cited = {fid for m in answer["metrics"] for fid in m["annual_fact_ids"]}
    recovery_report = {}
    if gap:
        missing = [t for t in trace if t['tool'] == 'facts' and t['arguments'].get('predicate') == 'revenue' and
                   t['arguments'].get('period') == 'FY2025' and t['response'].get('status') == 'not_extracted']
        recovered = [t for t in trace if t['tool'] == 'source_lookup' and t['response'].get('status') == 'recovered_candidate']
        if not missing or not recovered or missing[0]['step'] >= recovered[0]['step']:
            errors.append('missing_before_recovery_not_observed')
        original_path = root / 'data/research_data/google_cloud_spike' / run['input_run_id'] / 'snapshot.json'
        parent = json.loads(original_path.read_text())
        if digest(original_path.read_bytes()) != run['fixture']['parent_snapshot_sha256']:
            errors.append('parent_changed')
        expected = next(f for f in parent['facts'] if f['predicate'] == 'revenue' and f['period'] == 'FY2025')
        actual = [f for f in resolved['facts'] if f['predicate'] == 'revenue' and f['period'] == 'FY2025']
        if len(actual) != 1 or any(actual[0][k] != expected[k] for k in ('value','unit','subject_id')):
            errors.append('recovered_value_mismatch')
        if any(f['predicate'] == 'revenue' and f['period'] == 'FY2025' for f in snapshot['facts']):
            errors.append('fixture_did_not_remove_fact')
        recovery_report = {'recovery': {'missing_observed': bool(missing), 'successful_lookups': len(recovered),
                           'held_out_value_matches': 'recovered_value_mismatch' not in errors,
                           'parent_unchanged': 'parent_changed' not in errors, 'human_review': 'pending'}}
    return {"status": "passed" if not errors else "failed", "errors": errors, **recovery_report,
            "answer_sha256": digest((folder / "answer.json").read_bytes()),
            "input_snapshot_sha256": run["snapshot_sha256"], "model_rounds": len(rounds),
            "tool_calls": len(trace), "cited_annual_facts": len(cited), "checked_comparisons": len(comparisons),
            "human_review": "pending", "narrative_semantics": "not_automatically_verified",
            "limitations": ("Controlled one-value gap; fixed rule-based source recovery, not general search. Recovered data pending review."
                            if gap else "Saved action replay and arithmetic checks, not independent dataset validation. No missing-data scenario occurred in this live run.")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    folder = parser.parse_args().run_dir
    report = evaluate(folder)
    content = encoded(report)
    path = folder / "evaluation.json"
    if path.exists() and path.read_bytes() != content:
        raise FileExistsError("evaluation exists with different contents")
    if not path.exists():
        with path.open("xb") as f:
            f.write(content)
    print(content.decode())
    if report["errors"]:
        raise SystemExit(1)
