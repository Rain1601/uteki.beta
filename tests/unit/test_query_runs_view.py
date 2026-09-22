"""Saved-run viewer provenance and company boundaries; no model/SQL execution."""
import copy
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
import shutil

from apps.review_workbench.query_runs import collections, load_case, render_query_runs, render_turn, sql_rows

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / 'data/query_views'


class QueryRunViewTests(unittest.TestCase):
    def setUp(self):
        self.collection = collections(REGISTRY, 'alphabet')[0]

    def test_sql_rows_are_bound_to_recorded_selection_not_result_order(self):
        data = load_case(ROOT, self.collection, 'live-02', 'q1-margin')
        result = data['turns'][0]['result']
        trace = result['trace'][0]
        result['records'].reverse()
        _, rows = sql_rows(trace, result)
        self.assertEqual([r['metric_id'] for r in rows], ['revenue'])
        self.assertEqual(rows[0]['value_decimal'], '20028000000')
        changed = {**trace, 'parameters': ['different']}
        self.assertIsNone(sql_rows(changed, result)[1])

    def test_missing_and_other_company_selection_never_fall_back(self):
        self.assertFalse(collections(REGISTRY, 'independent-company'))
        with self.assertRaises(KeyError):
            render_query_runs(ROOT, REGISTRY, {'id': 'independent-company', 'name': 'Other'},
                {'collection': self.collection['id'], 'run': 'live-02', 'case': 'q1-margin'})
        for run, case in [('missing', 'q1-margin'), ('live-02', '../../.env')]:
            with self.assertRaises(KeyError):
                load_case(ROOT, self.collection, run, case)

    def test_untrusted_changed_artifact_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / 'run/case/session'
            folder.mkdir(parents=True)
            (folder / 'result.json').write_text('{}')
            manifest = {'files': {'result.json': sha256(b'original').hexdigest()}}
            (folder / 'manifest.json').write_text(json.dumps(manifest))
            config = {'company_id': 'acme', 'cases': [{'id': 'case'}], 'runs': [{'id': 'r', 'path': 'run',
                'session_manifest_hashes': {'case': sha256((folder / 'manifest.json').read_bytes()).hexdigest()}}]}
            with self.assertRaisesRegex(ValueError, 'artifact changed'):
                load_case(root, config, 'r', 'case')

    def test_formatting_only_is_verified_without_overwriting_history(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = copy.deepcopy(self.collection)
            run = next(r for r in config['runs'] if r['id'] == 'live-02')
            original = ROOT / run['path'] / 'q1-margin'
            run['path'] = 'copy'
            shutil.copytree(original, root / 'copy/q1-margin')
            result = root / 'copy/q1-margin/session/result.json'
            result.write_text(json.dumps(json.loads(result.read_text()), ensure_ascii=False))
            before = result.read_bytes()
            loaded = load_case(root, config, 'live-02', 'q1-margin')
            self.assertEqual(loaded['format_only_changes'], ['result.json'])
            self.assertEqual(result.read_bytes(), before)

    def test_all_six_historical_results_render_and_preserve_failed_verdict(self):
        for run in self.collection['runs']:
            for case in self.collection['cases']:
                with self.subTest(run=run['id'], case=case['id']):
                    output = render_query_runs(ROOT, REGISTRY, {'id': 'alphabet', 'name': 'Alphabet'},
                        {'collection': self.collection['id'], 'run': run['id'], 'case': case['id']})
                    self.assertIn('查询过程', output)
                    if case['id'] == 'clarify-period' and run['id'] == 'live-01':
                        self.assertIn('验收未通过', output)
                    if case['id'] == 'clarify-period' and run['id'] == 'live-02':
                        self.assertIn('未执行 SQL', output)

    def test_failed_tool_does_not_claim_zero_sql_and_source_text_is_escaped(self):
        data = load_case(ROOT, self.collection, 'live-01', 'q1-margin')
        html = render_turn(data['turns'][0], True)
        self.assertIn('SQL 轨迹未保存', html)
        turn = copy.deepcopy(data['turns'][0])
        turn['feedback']['message'] = '<script>bad()</script>'
        self.assertNotIn('<script>bad()</script>', render_turn(turn, True))
