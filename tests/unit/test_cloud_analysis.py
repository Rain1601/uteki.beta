import copy
import unittest
from pathlib import Path

from uteki.agents.cloud_analysis import AnalysisTools, load_approved, run_agent, validate_answer
from apps.review_workbench.cloud_analysis import render_cloud_analysis
from scripts.evaluate_cloud_analysis import evaluate

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "data/research_data/google_cloud_spike/run-9856300a8d74fa77"


class CloudAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot, _ = load_approved(RUN)

    def setUp(self):
        self.tools = AnalysisTools(self.snapshot, "2026-02-05")

    def prepare_answer(self):
        metrics = []
        for metric in ("revenue", "operating_income"):
            response = self.tools.call("facts", {"predicate": metric, "limit": 3})
            facts = sorted(response["results"], key=lambda f: f["period"])
            ids = [f["fact_id"] for f in facts]
            for fid in ids:
                self.tools.call("evidence", {"fact_id": fid})
            cids = [self.tools.call("compare", {"start_fact_id": ids[a], "end_fact_id": ids[b]})["comparison_id"]
                    for a, b in ((0, 1), (1, 2), (0, 2))]
            metrics.append({"predicate": metric, "annual_fact_ids": ids, "comparison_ids": cids})
        return {"metrics": metrics, "summary_zh": "收入与营业利润均增加。", "summary_en": "Both increased.",
                "limitations": ["FY2025 filing presentation only."]}

    def test_manifest_no_facts_and_pagination(self):
        self.assertNotIn("facts", self.tools.call("manifest", {}))
        result = self.tools.call("facts", {"predicate": "revenue"})
        self.assertEqual(len(result["results"]), 2)
        self.assertEqual(result["next_offset"], 2)

    def test_cannot_cite_unseen_fact_or_execute_unknown_tool(self):
        self.assertEqual(self.tools.call("evidence", {"fact_id": self.snapshot["facts"][1]["fact_id"]})["status"], "tool_error")
        self.assertEqual(self.tools.call("shell", {"command": "anything"})["status"], "tool_error")

    def test_calculation_and_provenance(self):
        answer = self.prepare_answer()
        c = self.tools.comparisons[answer["metrics"][0]["comparison_ids"][0]]
        self.assertEqual(c["delta"], 10141)
        self.assertEqual(c["growth_percent"], "30.65")
        self.assertEqual(len(c["evidence_ids"]), 2)
        validate_answer(answer, self.tools)

    def test_missing_is_not_source_absence(self):
        result = self.tools.call("facts", {"predicate": "revenue", "period": "Q1-2025"})
        self.assertEqual(result["status"], "not_extracted")
        self.assertEqual(self.tools.call("request_missing", {"predicate": "revenue", "period": "Q1-2025"})["status"], "recorded_only")

    def test_reject_uncited_and_wrong_comparison(self):
        answer = self.prepare_answer()
        self.tools.cited.clear()
        with self.assertRaises(ValueError):
            validate_answer(answer, self.tools)
        self.prepare_answer()
        answer["metrics"][0]["comparison_ids"][0] = answer["metrics"][1]["comparison_ids"][0]
        with self.assertRaises(ValueError):
            validate_answer(answer, self.tools)

    def test_nonpositive_base_is_explicit(self):
        self.prepare_answer()
        ids = sorted(self.tools.seen, key=lambda fid: self.tools.seen[fid]["period"])
        ids = [fid for fid in ids if self.tools.seen[fid]["predicate"] == "revenue"]
        self.tools.seen[ids[0]]["value"] = 0
        result = self.tools.compare(ids[0], ids[1])
        self.assertIsNone(result["growth_percent"])
        self.assertEqual(result["growth_status"], "nonpositive_base_not_comparable")

    def test_model_action_drives_dispatch_not_a_preset_trace(self):
        captured = []
        def complete(messages):
            captured.append(copy.deepcopy(messages))
            return {"action": "tools", "calls": [{"tool": "facts", "arguments": {"predicate": "capex"}}]}
        with self.assertRaisesRegex(ValueError, "round budget"):
            run_agent(complete, self.tools, max_rounds=1)
        self.assertEqual(self.tools.trace[0]["tool"], "facts")
        self.assertEqual(self.tools.trace[0]["arguments"]["predicate"], "capex")
        self.assertEqual(len(captured[0]), 2)
        self.assertNotIn("58,705", str(captured[0]))

    def test_budget_and_future_guard(self):
        with self.assertRaises(PermissionError):
            AnalysisTools(self.snapshot, "2025-12-31")
        with self.assertRaisesRegex(ValueError, "tool budget"):
            run_agent(lambda _: {"action": "tools", "calls": [{"tool": "manifest", "arguments": {}}]},
                      self.tools, max_calls=0)

    def test_unapproved_data_cannot_start(self):
        with self.assertRaises(PermissionError):
            load_approved(ROOT / "data/research_data/google_cloud_spike/run-ca8c3b123d597b5c")

    def test_saved_live_run_replays_and_evaluates(self):
        folder = ROOT / "experiments/cloud_analysis/analysis-a6a15b4ee5167df6"
        report = evaluate(folder)
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["checked_comparisons"], 6)
        self.assertEqual(report["cited_annual_facts"], 6)

    def test_analysis_view_is_separate_and_evidence_linked(self):
        page = render_cloud_analysis(ROOT / "experiments/cloud_analysis/analysis-a6a15b4ee5167df6", ROOT)
        self.assertIn("Uteki / Analysis", page)
        self.assertIn("A0 · 审核通过", page)
        self.assertIn("30.65%", page)
        self.assertIn("data-target='e1'", page)
        self.assertIn("模型首次输入", page)


if __name__ == "__main__":
    unittest.main()
