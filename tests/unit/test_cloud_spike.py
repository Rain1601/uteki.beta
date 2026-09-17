import copy
import json
import unittest
from pathlib import Path

from uteki.infrastructure.research_data.cloud_spike import CloudReader, extract, simulate

ROOT = Path(__file__).resolve().parents[2]


class CloudSpikeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = extract(ROOT / "data/source_documents/alphabet_2025_10k")

    def test_source_extraction_matches_candidate_reference(self):
        ref = json.loads((ROOT / "benchmarks/google_cloud_spike/v0.1-candidate/reference.json").read_text())
        facts = self.snapshot["facts"]
        self.assertEqual(len(facts), 7)
        self.assertEqual(facts[0]["value"], ref["offerings"])
        for f in facts[1:]:
            self.assertEqual(f["value"], ref["metrics"][f["predicate"]][f["period"]])
            self.assertEqual(f["unit"], ref["unit"])

    def test_same_source_has_same_snapshot(self):
        self.assertEqual(self.snapshot, extract(ROOT / "data/source_documents/alphabet_2025_10k"))

    def test_pagination_returns_all_and_only_matching_facts(self):
        reader = CloudReader(self.snapshot, as_of="2026-02-05")
        first = reader.facts(predicate="revenue", limit=2)
        second = reader.facts(predicate="revenue", limit=2, offset=first["next_offset"])
        self.assertEqual(len(first["results"] + second["results"]), 3)
        self.assertIsNone(second["next_offset"])
        self.assertEqual(reader.facts(predicate="revenue", period="Q1-2025")["status"], "not_extracted")
        self.assertEqual(reader.facts(predicate="capex")["status"], "unsupported")

    def test_historical_period_does_not_bypass_publication_date(self):
        with self.assertRaises(PermissionError):
            CloudReader(self.snapshot, as_of="2025-12-31")

    def test_trace_and_caller_are_isolated_from_snapshot(self):
        data = copy.deepcopy(self.snapshot)
        reader = CloudReader(data, as_of="2026-02-05")
        data["facts"].clear()
        response = reader.facts(predicate="revenue")
        response["results"].clear()
        self.assertEqual(len(reader.trace[0]["response"]["results"]), 2)
        self.assertEqual(reader.facts(predicate="revenue")["total"], 3)

    def test_simulation_reads_each_fact_evidence_and_requests_gap(self):
        trace = simulate(CloudReader(self.snapshot, as_of="2026-02-05"))
        self.assertEqual(trace[0]["tool"], "manifest")
        self.assertNotIn("facts", trace[0]["response"])
        self.assertEqual(sum(t["tool"] == "evidence" for t in trace), 7)
        self.assertEqual(trace[-1]["response"]["status"], "recorded_only")
        self.assertTrue(all(t["response"]["snapshot_id"] == self.snapshot["snapshot_id"] for t in trace))


if __name__ == "__main__":
    unittest.main()
