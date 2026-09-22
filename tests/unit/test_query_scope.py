"""Independent synthetic companies, periods and values; no Alphabet fixture."""
import json
from pathlib import Path
import tempfile
import unittest

import duckdb
from pydantic import ValidationError

from uteki.domain.research_data.query_contract import DataQuery, QueryResult, ResearchRecord, VERSION
from uteki.infrastructure.research_data.financial_records import digest
from uteki.infrastructure.research_data.query_dataset import DDL, save
from uteki.infrastructure.research_data.query_service import QueryDataPort
from uteki.infrastructure.research_data.adapters.legacy_alphabet import require_legacy_alphabet_source


class QueryScopeTests(unittest.TestCase):
    def test_legacy_adapters_reject_a_different_filing(self):
        with self.assertRaisesRegex(ValueError, 'pinned source'):
            require_legacy_alphabet_source({'content_sha256': '0' * 64, 'form': '10-K', 'period_end': '2031-12-31'})

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dataset = Path(tmp.name)
        sources = [
            {"source_snapshot_id": "acme-2031", "company_id": "acme", "form": "10-Q", "period_end": "2031-06-30", "available_at": "2031-07-20"},
            {"source_snapshot_id": "other-2030", "company_id": "other", "form": "10-Q", "period_end": "2030-06-30", "available_at": "2030-07-20"},
            {"source_snapshot_id": "other-call", "company_id": "other", "form": "EARNINGS_CALL", "period_end": "2031-06-30", "available_at": "2031-07-20"},
        ]
        metrics = {m: {"metric_id": m, "unit": "USD"} for m in ("revenue", "operating_income", "gross_profit")}
        db = duckdb.connect(str(self.dataset / "research.duckdb"))
        db.execute(DDL)
        for s in sources:
            db.execute("INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?)",
                       [s[k] for k in ("source_snapshot_id", "company_id", "form", "period_end", "available_at")] + [json.dumps(s)])
        for metric, value in (("revenue", "900"), ("operating_income", "135")):
            row = ResearchRecord(record_id=metric, record_type="metric", entity_id="acme-services", metric_id=metric,
                period={"kind": "quarter", "start": "2031-04-01", "end": "2031-06-30"}, value_kind="actual",
                value_decimal=value, value_relation="eq", unit="USD", accounting_basis="reported_segment",
                available_at="2031-07-20", source_snapshot_id="acme-2031", evidence_ids=(metric,),
                summary="Synthetic source observation", origin={}).model_dump(mode="json")
            db.execute("INSERT INTO observations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       [row["record_id"], row["entity_id"], metric, "quarter", "2031-04-01", "2031-06-30", "actual",
                        value, None, "eq", "USD", "reported_segment", "2031-07-20", "acme-2031", "candidate", json.dumps(row)])
            evidence = {"evidence_id": metric, "source_snapshot_id": "acme-2031", "quote": value}
            db.execute("INSERT INTO evidence VALUES (?, ?, ?)", [metric, "acme-2031", json.dumps(evidence)])
        db.close()
        save(self.dataset / "sources.json", sources)
        save(self.dataset / "metrics.json", metrics)
        for name, model in (("query", DataQuery), ("record", ResearchRecord), ("result", QueryResult)):
            save(self.dataset / f"schemas/{name}.schema.json", model.model_json_schema())
        save(self.dataset / "manifest.json", {"schema_version": VERSION, "snapshot_id": "synthetic-two-companies",
             "source_policy_id": "local-frozen-v1", "limits": ["Synthetic regression fixture"],
             "files": {str(p.relative_to(self.dataset)): digest(p.read_bytes()) for p in self.dataset.rglob("*") if p.is_file()}})
        self.port = QueryDataPort(self.dataset)
        self.addCleanup(self.port.close)

    def request(self, **kwargs):
        return {"query_id": "scope-test", "snapshot_id": self.port.snapshot_id, "knowledge_cutoff": "2031-07-21",
                "include_candidates": True, **kwargs}

    def record(self, entity, year=2031):
        return {"entity_id": entity, "metric_id": "gross_profit", "period": {
            "kind": "quarter", "start": f"{year}-04-01", "end": f"{year}-06-30"}}

    def test_schema_and_calculation_follow_dataset_entities(self):
        entities = {e["entity_id"]: e for e in self.port.get_schema()["entities"]}
        self.assertEqual(set(entities), {"acme", "acme-services", "other"})
        self.assertEqual(entities["acme-services"]["company_id"], "acme")
        result = self.port.query_data(self.request(calculations=[{"formula_id": "operating_margin",
            "entity_id": "acme-services", "periods": [self.record("acme-services")["period"]]}]))
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["computed_facts"][0]["display_decimal"], "15.00")
        self.assertEqual({r["entity_id"] for r in result["records"]}, {"acme-services"})
        self.assertTrue(all(e["source_snapshot_id"] == "acme-2031" for e in result["evidence"].values()))

    def test_other_company_or_call_cannot_establish_financial_coverage(self):
        for entity, year, expected in (("other", 2031, "source_missing"),
                                       ("other", 2030, "source_present_unprocessed"),
                                       ("acme-services", 2031, "source_present_unprocessed")):
            with self.subTest(entity=entity, year=year):
                result = self.port.query_data(self.request(records=[self.record(entity, year)]))
                self.assertEqual(result["selections"][0]["status"], expected)
                self.assertEqual(result["evidence"], {})

    def test_unknown_entity_and_blank_scope_are_not_defaulted(self):
        result = self.port.query_data(self.request(records=[self.record("alphabet")]))
        self.assertEqual(result["selections"][0]["status"], "unsupported")
        self.assertEqual(result["records"], [])
        with self.assertRaises(ValidationError):
            self.port.query_data(self.request(records=[self.record(" \t")]))

    def test_source_cutoff_remains_enforced_for_another_company(self):
        request = self.record("acme-services")
        request["metric_id"] = "revenue"
        result = self.port.query_data(self.request(records=[request], knowledge_cutoff="2031-07-19"))
        self.assertEqual(result["selections"][0]["status"], "not_available_at_cutoff")
        self.assertFalse(result["records"] or result["evidence"])
