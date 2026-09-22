"""Run the bounded, offline steps and prepare paired consumer inputs.

Evaluation references stay in this orchestrator; source extractors never read
them. All output directories are append-only. No model is called by this script.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import gzip
import json
from pathlib import Path

from uteki.agents.document_reader import DocumentReader
from uteki.infrastructure.research_data.cloud_spike import extract as old_extract
from uteki.infrastructure.research_data.financial_records import (
    FinancialRecordPort, compute_ytd_difference, digest, extract_financial_records,
)
from uteki.infrastructure.research_data.transcript_records import extract_transcript_records

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "experiments/research_data_quality/2026-09-22-execution/protocol.json"
BASELINE = ROOT / "experiments/research_data_quality/2026-09-22-step-00"
SPECS = {
    "annual": ("data/source_documents/alphabet_2025_10k", "indexes/v0.1"),
    "q1": ("data/document_library/alphabet/sources/alphabet-000165204426000048", "indexes/v0.4-candidate"),
    "q2": ("data/document_library/alphabet/sources/alphabet-000165204426000071", "indexes/v0.4-candidate"),
    "call": ("data/document_library/alphabet/sources/alphabet-2025q4-call", "indexes/v0.1-candidate"),
}
QUESTIONS = {
    "A1": "依据材料比较 Google Cloud 2025 与 2026 年 Q2 单季收入、营业利润和营业利润率，计算同比及利润率变化。另列 2026 上半年收入，说明它为何不能当成 Q2 单季收入。数字附原文引用，计算列操作数。",
    "A2": "依据 2025 Q4 电话会说明管理层的 2026 年 CapEx 指引、金额单位、适用期间和影响金额的限定。说明 Q&A 中 60%/40% 的资产构成及 just over half 的 ML compute 分配，能否据此推断 Cloud 占全公司 CapEx 超过一半？本材料能否回答管理层在 2026 Q2 电话会的解释？请给出依据与缺口。",
}


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")


def load(path):
    return json.loads(path.read_text())


def verify_sources():
    manifest = load(BASELINE / "manifest.json")
    for source in manifest["sources"]:
        for file in [source["raw_file"], source["source_manifest"], *source["index_files"]]:
            if digest((ROOT / file["path"]).read_bytes()) != file["sha256"]:
                raise ValueError("Step 0 input changed: " + file["path"])
        if source["eligible_for_new_comparison"]:
            path = ROOT / source["raw_file"]["path"]
            raw = gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes()
            if digest(raw) != source["declared_content_sha256"]:
                raise ValueError("Source integrity changed")
    return manifest


def run(output):
    source_manifest = verify_sources()
    if output.exists():
        raise FileExistsError("Use a new experiment directory")
    output.mkdir(parents=True)
    protocol = load(PROTOCOL)
    save(output / "protocol.json", protocol)
    save(output / "source-inventory.json", source_manifest)
    code_paths = [Path(__file__).resolve(), ROOT / "src/uteki/infrastructure/research_data/financial_records.py",
                  ROOT / "src/uteki/infrastructure/research_data/transcript_records.py",
                  ROOT / "src/uteki/agents/document_reader.py", ROOT / "src/uteki/agents/reading_groups.py"]
    code_hashes = {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in code_paths}
    for path in code_paths:
        target = output / "code" / path.name
        target.parent.mkdir(exist_ok=True)
        with target.open("xb") as f:
            f.write(path.read_bytes())
    start = datetime.now(timezone.utc).isoformat()
    results = {}
    current_baseline = old_extract(ROOT / SPECS["annual"][0])
    save(output / "step-00" / "current-rule-output.json", current_baseline)
    baseline_by_key = {(r["predicate"], r["period"]): Decimal(str(r["value"])) * 1000000
                       for r in current_baseline["facts"] if r["predicate"] != "offerings"}
    for name in ("annual", "q1", "q2"):
        folder, index = SPECS[name]
        result = extract_financial_records(ROOT / folder, ROOT / folder / index,
                                          metrics=["revenue", "operating_income"] if name == "annual" else None)
        results[name] = result
        save(output / ("step-01" if name == "annual" else "step-02") / (name + "-output.json"), result)
    differences = []
    for row in results["annual"]["records"]:
        period = "FY" + row["period"]["end"][:4]
        before = baseline_by_key[(row["metric"], period)]
        differences.append({"metric": row["metric"], "period": period, "before_usd": str(before),
                            "after_usd": row["value_decimal"], "numeric_equal": before == Decimal(row["value_decimal"]),
                            "after_record_id": row["record_id"], "evidence_occurrences": len(row["evidence_ids"]),
                            "new_contract": ["explicit_dates", "structured_dimensions", "raw_scale_and_sign",
                                             "table_header_checks", "record_vs_series_id"]})
    save(output / "step-01" / "diff-parent.json", differences)
    save(output / "step-01" / "diff-baseline.json", differences)
    numeric_checks = []
    for expected in protocol["reference_numeric_rows"]:
        matches = [r for r in results[expected["source"]]["records"] if
                   (r["entity_id"], r["metric"], r["period"]["start"], r["period"]["end"]) ==
                   (expected["entity"], expected["metric"], expected["start"], expected["end"])]
        numeric_checks.append({"expected": expected, "found_count": len(matches),
                               "record_ids": [r["record_id"] for r in matches],
                               "matched": len(matches) == 1 and matches[0]["unit"] == "USD"
                               and matches[0]["accounting_basis"] == ("reported_consolidated" if expected["entity"] == "alphabet" else "reported_segment")
                               and (matches[0]["period"]["kind"] == "instant") == (expected["kind"] == "instant")
                               and Decimal(matches[0]["value_decimal"]) == Decimal(expected["value_usd"]),
                               "review_basis": "preimplementation_source_review_not_blind_gold"})
    save(output / "numeric-reference-checks.json", numeric_checks)
    calculations = []
    for year in (2025, 2026):
        operands = [next(r for r in results[q]["records"] if r["metric"] == "capex_cash_payments"
                         and r["period"]["start"] == f"{year}-01-01") for q in ("q2", "q1")]
        calculations.append(compute_ytd_difference(*operands))
    save(output / "step-02" / "calculations.json", calculations)
    all_financial = [r for group in results.values() for r in group["records"]]
    port = FinancialRecordPort(all_financial)
    requests = [dict(entity_id="google-cloud", metric=metric, start="2026-04-01", end="2026-06-30", as_of="2026-07-23")
                for metric in ("revenue", "operating_income", "gross_profit")]
    requests.append({**requests[0], "as_of": "2026-07-22"})
    query_checks = [port.query(**query) for query in requests]
    save(output / "step-02" / "coverage-and-cutoff.json", query_checks)
    step2diff = {"unchanged_annual_numeric_rows": sum(c["numeric_equal"] for c in differences),
                 "newly_supported_quarterly_records": len(all_financial) - len(differences),
                 "derived_capex_quarters": calculations,
                 "before_status": "not_supported_by_existing_annual_structured_path; raw_document_reader_already_available",
                 "after_status": "typed_records_available; no_claim_of_prior_numeric_errors"}
    save(output / "step-02" / "diff-parent.json", step2diff)
    save(output / "step-02" / "diff-baseline.json", step2diff)
    call_folder, call_index = SPECS["call"]
    for step, expanded in (("step-03", False), ("step-04", True)):
        data = extract_transcript_records(ROOT / call_folder, ROOT / call_folder / call_index,
                                          expanded_guidance=expanded)
        results[step] = data
        save(output / step / "output.json", data)
    transcript_summary = dict(Counter(r["record_type"] for r in results["step-03"]["records"]))
    step3diff = {"before": "same source blocks and complete Q&A already readable; no typed guidance contract in this path",
                 "after_record_types": transcript_summary, "note": "topic-limited rule extraction, not exhaustive semantic recall"}
    save(output / "step-03" / "diff-parent.json", step3diff)
    save(output / "step-03" / "diff-baseline.json", {**step2diff, "transcript": step3diff})
    guidance_checks = []
    for row in results["step-04"]["records"]:
        if row["record_type"] != "Guidance":
            continue
        before = next(r for r in results["step-03"]["records"] if r["record_type"] == "Guidance"
                      and r["source_block_id"] == row["source_block_id"])
        guidance_checks.append({"source_block_id": row["source_block_id"], "range_unchanged": before["range"] == row["range"],
                                "before_context_blocks": len(before["evidence_ids"]), "after_context_blocks": len(row["evidence_ids"]),
                                "before_condition_links": before["condition_evidence_ids"], "after_condition_links": row["condition_evidence_ids"],
                                "changed_record": row})
    save(output / "step-04" / "diff-parent.json", guidance_checks)
    save(output / "step-04" / "diff-baseline.json", {**step2diff, "transcript": step3diff, "guidance": guidance_checks})
    prepare_consumer(output, results)
    summary = {"numeric_reference_agreement": {"matched": sum(c["matched"] for c in numeric_checks), "total": len(numeric_checks)},
               "annual_numeric_unchanged": all(c["numeric_equal"] for c in differences),
               "financial_records": len(all_financial), "financial_source_occurrences": sum(len(r["evidence"]) for r in (results[q] for q in ("annual", "q1", "q2"))),
               "financial_diagnostics": sum(len(results[q]["diagnostics"]) for q in ("annual", "q1", "q2")),
               "financial_conflicts": sum(len(results[q]["conflicts"]) for q in ("annual", "q1", "q2")),
               "transcript_record_types": transcript_summary, "guidance_checks": guidance_checks,
               "query_statuses": [q["status"] for q in query_checks], "calculations": calculations,
               "step_05": "packets_prepared_model_run_pending_credentials", "model_calls": 0,
               "review_status": "candidate_agent_source_review_not_human_gold", "excluded_sources": source_manifest["source_issues"]}
    save(output / "summary.json", summary)
    files = {str(p.relative_to(output)): digest(p.read_bytes()) for p in sorted(output.rglob("*")) if p.is_file()}
    save(output / "manifest.json", {"started_at": start, "completed_at": datetime.now(timezone.utc).isoformat(),
                                    "protocol_sha256": digest(PROTOCOL.read_bytes()), "code_hashes": code_hashes,
                                    "files": files, "status": "offline_steps_complete_consumer_pending", "model_calls": 0,
                                    "source_policy": "Step 0 immutable sources excluding mismatched release", "human_adoption": False})
    return summary


def prepare_consumer(output, results):
    q2folder, q2index = SPECS["q2"]
    callfolder, callindex = SPECS["call"]
    readers = {"q2": DocumentReader(ROOT / q2folder / q2index), "call": DocumentReader(ROOT / callfolder / callindex)}
    q2table = next(b for b in readers["q2"].blocks if b["type"] == "table"
                   and "Revenues:" in b["text"] and "Operating income (loss):" in b["text"] and "Google Cloud" in b["text"])
    root_node = next(n["node_id"] for n in readers["q2"].nodes.values() if n["kind"] == "document")
    table_context = readers["q2"].read(root_node, q2table["block_id"], 1)["blocks"]
    # The preceding prose carries the scale; the table alone only shows '$'.
    # Supply it to BOTH arms, without changing the underlying reader or indexes.
    position = readers["q2"].positions[q2table["block_id"]]
    prefix = readers["q2"].blocks[max(0, position - 2):position]
    if not any('in millions' in b['text'] for b in prefix):
        raise ValueError('Segment table unit context must be reviewed')
    included = {b['block_id'] for b in table_context}
    table_context = [b for b in prefix if b['block_id'] not in included] + table_context
    call_context = [b for b in readers["call"].blocks if b.get("exchange_id") == "qa-06"
                    or b["block_id"] in ("block-000019-229fa8b5", "block-000151-be80bd28", "block-000152-b7a839f7", "block-000153-938fcda2")]
    for case, key, blocks in (("A1", "q2", table_context), ("A2", "call", call_context)):
        reader = readers[key]
        doc_id = next(s["document_id"] for s in load(BASELINE / "manifest.json")["sources"]
                      if s["index_id"] == reader.index["index_id"])
        source_blocks = [{"document_id": doc_id, "index_id": reader.index["index_id"],
                          **{k: b.get(k) for k in ("block_id", "text", "text_hash", "table", "reported_page", "pdf_page", "speaker", "speaker_role", "exchange_id")}}
                         for b in blocks]
        raw = {"source_policy": "Only these frozen excerpts. Filings and call refer to their own periods; no Q2 call exists in inputs.",
               "blocks": source_blocks}
        if case == "A1":
            typed_records = [r for r in results["q2"]["records"] if r["metric"] in ("revenue", "operating_income")]
        else:
            typed_records = [r for r in results["step-04"]["records"] if r["record_type"] == "Guidance"
                             or (r["record_type"] == "QAExchange" and r["exchange_id"] == "qa-06")]
        block_ids = {b["block_id"] for b in blocks}
        evidence_source = results["q2"] if case == "A1" else results["step-04"]
        locators = {eid: {k: ev.get(k) for k in ("block_id", "document_id", "index_id", "quote", "cell")}
                    for eid, ev in evidence_source["evidence"].items() if ev["block_id"] in block_ids}
        typed = {**raw, "records": typed_records, "record_evidence_locators": locators,
                 "record_policy": "Records are candidate normalized data. Verify against supplied source blocks. Management guidance is not an actual financial observation."}
        for arm, packet in (("before", raw), ("after", typed)):
            text = json.dumps(packet, ensure_ascii=False, separators=(",", ":"))
            if len(text) > 65000:
                raise ValueError("Consumer packet exceeds preregistered input limit")
            save(output / "step-05" / case / (arm + "-input.json"), packet)
        save(output / "step-05" / case / "comparison-design.json",
             {"question": QUESTIONS[case], "same_source_blocks": True,
              "intervention": "Add verified typed records while preserving identical source evidence",
              "before_chars": len(json.dumps(raw, ensure_ascii=False, separators=(",", ":"))),
              "after_chars": len(json.dumps(typed, ensure_ascii=False, separators=(",", ":"))),
              "note": "One-turn fixed-input consumption test. No autonomous retrieval or measured follow-up reads; chars are not tokens."})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    preexisting = args.output.exists()
    try:
        summary = run(args.output)
    except Exception as exc:
        if not preexisting and args.output.exists() and not (args.output/'manifest.json').exists() and not (args.output/'failure.json').exists():
            save(args.output/'failure.json', {'status':'failed', 'error_type':type(exc).__name__, 'reason':str(exc)[:300]})
        raise
    print(json.dumps({k: summary[k] for k in ("numeric_reference_agreement", "financial_records", "transcript_record_types", "step_05")}, ensure_ascii=False))
