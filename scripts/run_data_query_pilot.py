"""Build the local query pilot and save every input, result and executed plan.

No model, external retrieval or production publication. Review assertions stay
in this harness and are not inputs to the data query service.
"""
import argparse
import json
from pathlib import Path

from uteki.infrastructure.research_data.financial_records import digest
from uteki.infrastructure.research_data.query_dataset import build_dataset, save
from uteki.infrastructure.research_data.query_service import QueryDataPort

ROOT = Path(__file__).resolve().parents[1]


def period(year, kind="quarter"):
    return {"kind": kind, "start": f"{year}-04-01" if kind == "quarter" else f"{year}-01-01",
            "end": f"{year}-12-31" if kind == "year" else f"{year}-06-30"}


def record(metric, year=2026, entity="google-cloud", kind="quarter", value_kind="actual"):
    return {"entity_id": entity, "metric_id": metric, "period": period(year, kind), "value_kind": value_kind}


def run(output):
    if output.exists():
        raise FileExistsError("use a new pilot directory")
    output.mkdir(parents=True)
    manifest = build_dataset(ROOT, output / "dataset", spec=ROOT / "experiments/data_agent_query/specs/alphabet-reviewed-v1.json")
    with QueryDataPort(output / "dataset") as port:
        save(output / "step-01/schema.json", port.get_schema())
        save(output / "step-01/coverage.json", port.discover_data(knowledge_cutoff="2026-09-22", include_candidates=True))
        normalized = json.loads((output / "dataset/records.json").read_text())["rows"]
        comparisons = []
        for r in normalized:
            raw = r["origin"]["raw_record"]
            comparisons.append({"record_id": r["record_id"], "metric_id": r["metric_id"],
                                "source_artifact": r["origin"]["artifact"],
                                "before": {k:raw[k] for k in ("value", "value_decimal", "unit", "period", "kind", "dimensions") if k in raw},
                                "after": {k:r[k] for k in ("value_decimal", "value_relation", "unit", "period", "period_resolution", "value_kind", "denominator", "modality", "dimensions")},
                                "notes": r["normalization_notes"]})
        save(output / "step-01/normalization-diff.json", comparisons)
        financial = {
            "question": "比较 Google Cloud 2025/2026 Q2 收入、营业利润和利润率，计算同比与利润率变化；另列 2026 H1 收入。",
            "records": [record("revenue", kind="ytd")],
            "calculations": [{"formula_id": "operating_margin", "entity_id": "google-cloud", "periods": [period(y)]} for y in (2025, 2026)]
                + [{"formula_id": f, "entity_id": "google-cloud", "periods": [period(2025), period(2026)]}
                   for f in ("revenue_yoy", "operating_income_yoy", "operating_margin_delta_pp")],
        }
        mixed = {"question": "列出 2026 CapEx 指引与原文条件，并回读 Q&A 核查 ML 算力分配和投资构成。",
                 "records": [record("capex_guidance", entity="alphabet", kind="year", value_kind="management_guidance"),
                             record("cloud_ml_compute_share", kind="year", value_kind="management_guidance"),
                             record("investment_mix_outlook", entity="alphabet", kind="year", value_kind="management_guidance")],
                 "documents": [{"company_id": "alphabet", "form": "EARNINGS_CALL", "period_end": "2025-12-31", "phrase": p} for p in ("timing of cash payments", "just over half")]}
        cases = {
            "step-02/financial": financial,
            "step-03/mixed": mixed,
            "step-03/missing-call": {"question": "查 2026 Q2 电话会中的 Cloud 解释", "documents": [{"company_id": "alphabet", "form": "EARNINGS_CALL", "period_end": "2026-06-30", "phrase": "Cloud"}]},
            "step-03/not-structured": {"records": [record("gross_profit")]},
            "step-03/cutoff": {"records": [record("revenue")], "knowledge_cutoff": "2026-07-22"},
            "step-03/candidate-filter": {"records": [record("revenue")], "include_candidates": False},
            "step-03/unresolved-period": {"records": [{"entity_id": "google-cloud", "metric_id": "cloud_growth_outlook", "period": None, "value_kind": "management_guidance"}]},
        }
        results = {}
        for name, params in cases.items():
            request = {"query_id": name.split("/")[-1], "snapshot_id": port.snapshot_id, "knowledge_cutoff": "2026-09-22",
                       "include_candidates": True, "source_policy_id": "local-frozen-v1", **params}
            save(output / name / "request.json", request)
            result = port.query_data(request)
            save(output / name / "result.json", result)
            save(output / name / "trace.json", result["trace"])
            results[name] = result
        final = results["step-02/financial"]
        assert [c["display_decimal"] for c in final["computed_facts"]] == ["20.74", "35.59", "81.80", "211.89", "14.84"]
        assert final["status"] == results["step-03/mixed"]["status"] == "complete"
        assert results["step-03/missing-call"]["gaps"][0]["reason"] == "source_missing"
        summary = {"snapshot_id": port.snapshot_id, "record_count": manifest["record_count"], "source_count": manifest["source_count"],
                   "evidence_count": manifest["evidence_count"], "model_calls": 0, "status": "local_pilot_complete_candidate_only",
                   "scope": "Typed query plans supplied by the harness; no autonomous NL planner or cross-model evaluation",
                   "cases": {key: {"status": value["status"], "record_count": len(value["records"]),
                                   "computed_facts": len(value["computed_facts"]), "gaps": value["gaps"]} for key,value in results.items()},
                   "financial_results": final["computed_facts"],
                   "numeric_values_preserved": all(r["value_decimal"] == r["origin"]["raw_record"]["value_decimal"] for r in normalized if "value_decimal" in r["origin"]["raw_record"]),
                   "remaining": ["General natural-language planning", "OCR and external acquisition", "MCP/HTTP adapter", "independent cross-company and cross-Agent evaluation"]}
        save(output / "summary.json", summary)
    runtime_files = [ROOT/"scripts/run_data_query_pilot.py", ROOT/"scripts/query_research_data.py",
                     *sorted((ROOT/"src/uteki/infrastructure/research_data").glob("query_*.py")),
                     *sorted((ROOT/"src/uteki/infrastructure/research_data/adapters").glob("*.py")),
                     ROOT/"src/uteki/domain/research_data/query_contract.py", ROOT/"tests/unit/test_query_data.py", ROOT/"pyproject.toml"]
    save(output / "run-manifest.json", {"runtime_hashes": {str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in runtime_files},
                                      "files": {str(p.relative_to(output)):digest(p.read_bytes()) for p in sorted(output.rglob("*")) if p.is_file()},
                                      "model_calls": 0, "adoption": "candidate only"})
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = run(args.output)
    print(json.dumps({k:v for k,v in summary.items() if k not in ("financial_results", "cases")}, ensure_ascii=False, indent=2))
