import copy
import json
import tempfile
import unittest
from pathlib import Path

from uteki.infrastructure.research_data.cloud_llm import materialize, prepare
from apps.review_workbench.cloud_spike import approved_review, render_cloud_spike

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/source_documents/alphabet_2025_10k"


class CloudLLMTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle, cls.manifest, cls.blocks = prepare(SOURCE)
        # Synthetic model output for validation tests; never used as a live run.
        cls.output = {"facts": [{"subject_id": "google-cloud", "predicate": "revenue",
            "period": "FY2025", "value": 58705, "unit": "USD millions",
            "block_id": "block-000914-d9c3ca1b", "quote": "58,705",
            "cell": {"row": 5, "column": 15}, "year_cell": {"row": 2, "column": 15}}], "unknowns": []}

    def convert(self, output):
        return materialize(output, self.bundle, self.manifest, self.blocks)

    def test_deterministic_preparation_preserves_whole_table_and_source_identity(self):
        self.assertEqual(self.bundle, prepare(SOURCE)[0])
        table = next(b for b in self.bundle["blocks"] if b["block_id"] == "block-000914-d9c3ca1b")
        self.assertTrue(any(c["text"] == "Google Services" for c in table["cells"]))
        self.assertTrue(any(c.get("xbrl", {}).get("scale") == "6" for c in table["cells"]))
        self.assertNotIn("reference", self.bundle)

    def test_valid_evidence_materialized_without_completeness_claim(self):
        snapshot = self.convert(self.output)
        self.assertEqual(snapshot["facts"][0]["value"], 58705)
        self.assertIn("require review", snapshot["coverage"]["status"])
        self.assertEqual(snapshot, self.convert(self.output))

    def test_reject_wrong_numeric_fact(self):
        for field, value in (("value", 58706), ("unit", "USD"), ("period", "FY2024"),
                             ("subject_id", "alphabet"), ("predicate", "operating_income"),
                             ("quote", "58,706"), ("value", True)):
            with self.subTest(field=field, value=value):
                output = copy.deepcopy(self.output)
                output["facts"][0][field] = value
                with self.assertRaises(ValueError):
                    self.convert(output)

    def test_reject_unretrieved_evidence(self):
        output = copy.deepcopy(self.output)
        output["facts"][0]["block_id"] = "invented"
        with self.assertRaises(KeyError):
            self.convert(output)

    def test_alternative_revenue_table_is_valid_evidence(self):
        output = copy.deepcopy(self.output)
        output["facts"][0]["block_id"] = "block-000790-942753de"
        output["facts"][0]["cell"]["row"] = 9
        self.assertEqual(self.convert(output)["facts"][0]["value"], 58705)

    def test_reject_duplicates_and_empty_response(self):
        output = copy.deepcopy(self.output)
        output["facts"] *= 2
        with self.assertRaises(ValueError):
            self.convert(output)
        with self.assertRaises(ValueError):
            self.convert({"facts": [], "unknowns": []})

    def test_reject_unverified_scale(self):
        bundle = copy.deepcopy(self.bundle)
        table = next(b for b in bundle["blocks"] if b["block_id"] == "block-000914-d9c3ca1b")
        for c in table["cells"]:
            if c["row"] == 5 and c["column"] == 15:
                c["xbrl"]["scale"] = "3"
        with self.assertRaises(ValueError):
            materialize(self.output, bundle, self.manifest, self.blocks)

    def test_rule_inspector_keeps_version_and_evaluation(self):
        run = ROOT / "data/research_data/google_cloud_spike/run-ca8c3b123d597b5c"
        page = render_cloud_spike(run, SOURCE)
        self.assertIn("规则提取", page)
        self.assertIn("与候选参考差异 0 项", page)
        self.assertIn("run-ca8c3b123d597b5c", page)
        self.assertIsNone(approved_review(run))

    def test_reviewed_snapshot_displays_approval(self):
        run = ROOT / "data/research_data/google_cloud_spike/run-9856300a8d74fa77"
        self.assertEqual(approved_review(run)["decision"], "approved")
        self.assertIn("独立提取 · 审核通过", render_cloud_spike(run, SOURCE))

    def test_approval_does_not_transfer_to_changed_snapshot(self):
        original = ROOT / "data/research_data/google_cloud_spike/run-9856300a8d74fa77"
        decision = approved_review(original)
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp) / "data/research_data/google_cloud_spike" / original.name
            run.mkdir(parents=True)
            (run / "snapshot.json").write_text('{"changed": true}')
            folder = Path(temp) / "experiments/google_cloud_spike" / original.name / "reviews"
            folder.mkdir(parents=True)
            (folder / "decision.json").write_text(json.dumps(decision))
            self.assertIsNone(approved_review(run))


if __name__ == "__main__":
    unittest.main()
