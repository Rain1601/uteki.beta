"""Frozen walkthrough truthfulness, isolation, integrity and read-only behavior."""
import copy
from hashlib import sha256
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from apps.review_workbench.acceptance_view import (
    load_walkthrough, registrations, render_acceptance, read_panel, source_link,
)
from apps.review_workbench.app import make_handler, DEFAULT_DATA
from uteki.domain.research_data.evidence_package import EvidencePackage

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / 'data/acceptance_views'
COMPANY = {'id': 'alphabet', 'name': 'Alphabet'}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return sha256(path.read_bytes()).hexdigest()


def synthetic(root):
    """An independent company/year with no fallback to the real pilot."""
    scope = {'execution_schema_version': 'research-execution-v1', 'snapshot_id': 'acme-2031',
             'company_ids': ['acme'], 'source_snapshot_ids': ['acme-annual'],
             'knowledge_cutoff': '2032-03-01', 'source_policy_id': 'local-frozen-v1', 'include_candidates': True}
    request = {'agent_schema_version': 'data-agent-query-v0.3', 'question': 'Inspect synthetic input.', 'scope': scope}
    source = {'source_snapshot_id': 'acme-annual', 'company_id': 'acme', 'form': '10-K',
              'period_end': '2031-12-31', 'available_at': '2032-02-01', 'source_url': 'https://example.invalid/acme'}
    outline = {'action': 'outline_source', 'outline': {'source_snapshot_id': 'acme-annual'}}
    finish = {'action': 'finish', 'answer_parts': [{'requested_information': 'No body read', 'record_ids': []}]}
    package = EvidencePackage(bundle_id='acme-package', scope=scope, source_companies={'acme-annual': 'acme'}).model_dump(mode='json')
    result = {'request': request, 'status': 'partial', 'gaps': [{'reason': 'body_not_read'}],
              'evidence_package': {'bundle_id': package['bundle_id']},
              'trace': [{'step': 1, 'tool': 'outline_source', 'result_file': 'turn-01/tool-result.json'}, {'step': 2, 'tool': 'finish'}]}
    session = {'request.json': request, 'result.json': result, 'evidence-package.json': package,
               'turn-01/decision.json': outline, 'turn-01/tool-result.json': {'source': source, 'nodes': []},
               'turn-02/decision.json': finish}
    files = {name: write_json(root / 'run/session' / name, value) for name, value in session.items()}
    manifest = write_json(root / 'run/session/manifest.json', {'files': files})
    spec = write_json(root / 'run/spec.json', {'dataset': 'dataset', 'request': request, 'steps': [{'decision': outline}, {'finish_references': 'No body read'}]})
    verification = write_json(root / 'run/verification.json', {'mode': 'scripted_offline_tools', 'model_calls': 0})
    final = write_json(root / 'run/final-verification.json', {'model_calls': 0, 'checks': {}})
    dataset = {name: write_json(root / 'dataset' / name, value) for name, value in {'sources.json': [source], 'records.json': {'rows': []}}.items()}
    dataset_manifest = write_json(root / 'dataset/manifest.json', {'snapshot_id': scope['snapshot_id'], 'files': dataset})
    registration = {'schema_version': 'acceptance-view-v1', 'id': 'acme-check', 'company_id': 'acme', 'title': ['独立样例', 'Independent fixture'],
                    'run': {'path': 'run', 'manifest_sha256': manifest, 'spec_sha256': spec, 'verification_sha256': verification, 'final_verification_sha256': final},
                    'dataset': {'path': 'dataset', 'manifest_sha256': dataset_manifest}}
    write_json(root / 'registry/acme-check.json', registration)
    return registration


class AcceptanceViewTests(unittest.TestCase):
    def setUp(self):
        self.registration = registrations(REGISTRY, 'alphabet')[0]

    def test_real_walkthrough_preserves_values_modalities_and_limits(self):
        html = render_acceptance(ROOT, REGISTRY, COMPANY, 'evidence-package-v1')
        for value in ('175,000,000,000', '185,000,000,000', '23.69', '13,910', '58,705',
                      '保留 4 个缺口', '语义', '未评估', '历史模型提取 · 2', '模型摘要 · 0',
                      '正文返回（含标题）', '仅图片引用', '0 次模型调用', '这轮没有重新提取'):
            self.assertTrue(value in html, value)
        data = load_walkthrough(ROOT, self.registration)
        image = data['turns'][2]
        rendered = read_panel(image['decision'], image['result'], data['turns'])
        self.assertIn('替代文字', rendered)
        self.assertNotIn('<blockquote>2949</blockquote>', rendered)
        self.assertEqual(len(data['records']), 19)

    def test_unknown_company_collection_and_paths_never_fall_back(self):
        self.assertEqual(registrations(REGISTRY, 'other'), [])
        for company, collection in [({'id':'other','name':'Other'}, 'evidence-package-v1'), (COMPANY, '../../.env')]:
            with self.assertRaises(KeyError):
                render_acceptance(ROOT, REGISTRY, company, collection)
        bad = copy.deepcopy(self.registration)
        bad['run']['path'] = '../outside'
        with self.assertRaises(ValueError):
            load_walkthrough(ROOT, bad)
        listing = render_acceptance(ROOT, REGISTRY, COMPANY)
        self.assertNotIn('id="walkthrough"', listing)

    def test_changed_run_artifact_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registration = synthetic(root)
            (root / 'run/session/result.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'artifact changed'):
                load_walkthrough(root, registration)

    def test_changed_dataset_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registration = synthetic(root)
            (root / 'dataset/records.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'Dataset artifact changed'):
                load_walkthrough(root, registration)

    def test_scope_and_execution_mode_cannot_be_relabelled(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registration = synthetic(root)
            wrong = copy.deepcopy(registration)
            wrong['company_id'] = 'other'
            with self.assertRaisesRegex(ValueError, 'scope'):
                load_walkthrough(root, wrong)
            registration['run']['verification_sha256'] = write_json(root / 'run/verification.json', {'mode': 'live', 'model_calls': 1})
            with self.assertRaisesRegex(ValueError, 'offline scripted'):
                load_walkthrough(root, registration)

    def test_independent_company_year_and_incomplete_run_render_without_mutation_or_sql(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            synthetic(root)
            before = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            with patch('duckdb.connect', side_effect=AssertionError('SQL must not run in a replay view')):
                html = render_acceptance(root, root / 'registry', {'id':'acme','name':'Acme'}, 'acme-check')
            self.assertIn('2031-12-31', html)
            self.assertIn('运行缺口 1', html)
            self.assertIn('partial', html)
            self.assertIn('2 次决策', html)
            self.assertNotIn('alphabet', html.lower())
            after = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            self.assertEqual(before, after)

    def test_untrusted_source_text_and_urls_are_not_executable(self):
        data = load_walkthrough(ROOT, self.registration)
        turn = copy.deepcopy(data['turns'][1])
        turn['result']['blocks'][0]['text'] = '<script>bad()</script>'
        html = read_panel(turn['decision'], turn['result'], data['turns'])
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<script>bad()', html)
        self.assertNotIn('href=', source_link({'source_url':'javascript:bad()', 'form':'<img>'}))

    def test_route_selection_and_workspace_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            handler = make_handler(DEFAULT_DATA, Path(directory) / 'state.json')
            for url, status in [('/companies/alphabet/data/acceptance?collection=evidence-package-v1', 200),
                                ('/companies/alphabet/data/acceptance?collection=unknown', 404),
                                ('/companies/alphabet/data/acceptance?collection=evidence-package-v1&collection=other', 404),
                                ('/companies/alphabet/data/acceptance?run=unknown', 404),
                                ('/companies/alphabet/data', 200)]:
                request = object.__new__(handler)
                request.path, request.wfile, request.headers = url, io.BytesIO(), {}
                response = {}
                request.send_response = lambda value: response.update(status=value)
                request.send_error = lambda value, *args: response.update(status=value)
                request.send_header = lambda *args: None
                request.end_headers = lambda: None
                request.do_GET()
                self.assertEqual(response['status'], status, url)
                if url == '/companies/alphabet/data':
                    self.assertIn('/data/acceptance', request.wfile.getvalue().decode())
