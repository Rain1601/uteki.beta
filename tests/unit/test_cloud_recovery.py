import copy
import json
import tempfile
import unittest
from pathlib import Path

from uteki.agents.cloud_analysis import load_approved
from uteki.agents.cloud_recovery import RecoveryTools
from uteki.infrastructure.research_data.cloud_recovery import withhold_fact, recover_from_source
from apps.review_workbench.cloud_analysis import analysis_approval, render_cloud_analysis
from scripts.evaluate_cloud_analysis import evaluate

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'data/source_documents/alphabet_2025_10k'
A0 = ROOT / 'experiments/cloud_analysis/analysis-a6a15b4ee5167df6'
A1 = ROOT / 'experiments/cloud_analysis/analysis-9373e1c4632a063d'


class RecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original, _ = load_approved(ROOT / 'data/research_data/google_cloud_spike/run-9856300a8d74fa77')
        cls.gap = withhold_fact(cls.original)

    def setUp(self):
        self.tools = RecoveryTools(self.gap, '2026-02-05', SOURCE)

    def test_gap_removes_fact_and_unused_evidence_without_mutating_original(self):
        self.assertEqual(len(self.original['facts']), 7)
        self.assertEqual(len(self.gap['facts']), 6)
        self.assertNotEqual(self.gap['snapshot_id'], self.original['snapshot_id'])
        self.assertFalse(any(f['predicate'] == 'revenue' and f['period'] == 'FY2025' for f in self.gap['facts']))
        self.assertNotIn('block-000790-942753de-r9-c15', self.gap['evidence'])

    def test_recovery_requires_observed_gap(self):
        result = self.tools.call('source_lookup', {'predicate': 'revenue', 'period': 'FY2025'})
        self.assertEqual(result['status'], 'tool_error')

    def test_recovers_from_raw_source_with_new_evidence_and_pending_review(self):
        self.tools.call('facts', {'predicate':'revenue','period':'FY2025'})
        result = self.tools.call('source_lookup', {'predicate':'revenue','period':'FY2025'})
        f = result['results'][0]
        self.assertEqual(f['value'], 58705)
        self.assertEqual(f['review_status'], 'pending')
        self.assertIn('block-000914', f['evidence_ids'][0])
        evidence = self.tools.call('evidence', {'fact_id': f['fact_id']})
        self.assertEqual(evidence['results'][0]['quote'], '58,705')
        self.assertEqual(len(self.tools.resolved_snapshot()['facts']), 7)
        self.assertEqual(len(self.gap['facts']), 6)

    def test_unsupported_period_is_not_absence_claim(self):
        result = recover_from_source(SOURCE, self.original['source_sha256'], 'revenue', 'Q1-2025')
        self.assertEqual(result['status'], 'unsupported_scope')
        self.assertEqual(result['results'], [])

    def test_wrong_source_hash_fails(self):
        with self.assertRaises(ValueError):
            recover_from_source(SOURCE, 'wrong', 'revenue', 'FY2025')

    def test_analysis_review_is_artifact_pinned(self):
        review = analysis_approval(A0)
        self.assertEqual(review['decision'], 'approved')
        self.assertIsNone(analysis_approval(A1))
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / A0.name
            (folder / 'reviews').mkdir(parents=True)
            for name in review['artifact_sha256']:
                (folder / name).write_bytes((A0 / name).read_bytes())
            (folder / 'reviews/decision.json').write_text(json.dumps(review))
            self.assertIsNotNone(analysis_approval(folder))
            (folder / 'answer.json').write_text('{}')
            self.assertIsNone(analysis_approval(folder))

    def test_live_recovery_and_ui(self):
        report = evaluate(A1)
        self.assertEqual(report['errors'], [])
        self.assertTrue(report['recovery']['missing_observed'])
        self.assertTrue(report['recovery']['parent_unchanged'])
        page = render_cloud_analysis(A1, ROOT)
        self.assertIn('A1 · 待审核', page)
        self.assertIn('原文重新提取 · 待审核', page)
        self.assertIn('从原文补取', page)
