import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts'))
import codex_hypothesis_mvp as reader
import render_hypothesis_mvp as report


class HypothesisMVPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.out = Path(self.temp.name)/'experiment'
        shutil.copytree(reader.OUT, self.out)
        self.patch_reader = patch.object(reader, 'OUT', self.out)
        self.patch_report = patch.object(report, 'OUT', self.out)
        self.patch_reader.start()
        self.patch_report.start()

    def tearDown(self):
        self.patch_reader.stop()
        self.patch_report.stop()
        self.temp.cleanup()

    def test_frozen_sources_and_period_calculations(self):
        stages, metrics, checks = report.validate()
        self.assertEqual(sum(c['citations'] for c in checks['stages']),30)
        self.assertEqual(metrics[0]['simplified_fcf'],[72764,73266])
        self.assertEqual(metrics[1]['simplified_fcf'],[18953,10116])
        self.assertEqual(metrics[2]['simplified_fcf'],[24254,4261])
        self.assertAlmostEqual(metrics[2]['cloud_growth_pct'],81.796829125)
        self.assertEqual(metrics[2]['cloud_revenue'],[13624,24768])
        self.assertEqual(metrics[2]['cash_period'],'H1 2025 / H1 2026')
        page=report.render(stages,metrics,checks)
        self.assertIn('review-notes.json',page)
        self.assertIn('data-evidence="C11"',page)
        self.assertIn('source#block-000484-fb81773c',page)

    def test_answer_tampering_is_detected(self):
        with (self.out/'annual/answer.json').open('a') as f:
            f.write(' ')
        with self.assertRaises(AssertionError):
            report.validate()
        with self.assertRaises(ValueError):
            reader.stage_material('q1')

    def test_read_tampering_is_detected(self):
        with (self.out/'annual/reads/001.json').open('a') as f:
            f.write(' ')
        with self.assertRaises(AssertionError):
            report.validate()

    def test_future_material_injection_is_detected(self):
        p=self.out/'annual/materials.json'
        data=json.loads(p.read_text())
        data['documents'].append(json.loads((self.out/'q2/materials.json').read_text())['documents'][-1])
        p.write_text(json.dumps(data))
        with self.assertRaises(AssertionError):
            report.validate()

    def test_q1_is_locked_without_annual_freeze(self):
        (self.out/'annual/frozen.json').unlink()
        with self.assertRaises(FileNotFoundError):
            reader.stage_material('q1')

    def test_frozen_stage_rejects_more_reads(self):
        with patch.object(sys,'argv',['reader','annual','outline']):
            with self.assertRaisesRegex(ValueError,'Stage is frozen'):
                reader.main()


if __name__ == '__main__':
    unittest.main()
