"""Read-only grid integrity, real lineage, and independent company boundaries."""
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

import duckdb

from apps.review_workbench.dataset_view import read_dataset, render_dataset, render_block
from apps.review_workbench.query_runs import collections

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / 'data/query_views'


class DatasetViewTests(unittest.TestCase):
    def setUp(self):
        self.collection = collections(REGISTRY, 'alphabet')[0]

    def test_actual_rows_and_physical_values_match_without_mutation(self):
        folder = ROOT / self.collection['dataset']['path']
        before = sha256((folder / 'research.duckdb').read_bytes()).hexdigest()
        data = read_dataset(ROOT, self.collection)
        self.assertEqual((len(data['records']), len(data['sources']), len(data['evidence'])), (37, 4, 52))
        for physical, record in zip(data['physical'], data['records']):
            self.assertEqual(physical['record_id'], record['record_id'])
            for key in ('value_decimal', 'upper_decimal'):
                self.assertEqual(physical[key], Decimal(record[key]) if record[key] is not None else None)
        self.assertIn(('observations', 'value_decimal', 'DECIMAL(38,12)', 'YES'), data['columns'])
        self.assertEqual(sha256((folder / 'research.duckdb').read_bytes()).hexdigest(), before)

    def test_lineage_preserves_scale_and_nonexact_semantics(self):
        company = {'id': 'alphabet', 'name': 'Alphabet'}
        financial = render_dataset(ROOT, REGISTRY, company, self.collection['id'], 'obs-18a5d78f90816dcd19b2')
        for text in ('20,028', '20028000000', '<th>scale</th><td>6', 'us-gaap:StatementBusinessSegmentsAxis'):
            self.assertIn(text, financial)
        threshold = render_dataset(ROOT, REGISTRY, company, self.collection['id'], 'qr-e6bf14c5f0c133c7f61559d9')
        for text in ('&gt; 50', 'total_ml_compute', 'expected', 'just over half', '还没有自动增量同步', '尚未完成全文信息损耗的定量评估'):
            self.assertIn(text, threshold)

    def test_unknown_record_and_other_company_do_not_fall_back(self):
        for company, record in [('another-company', None), ('alphabet', 'unknown'), ('alphabet', '../../.env')]:
            with self.subTest(company=company, record=record), self.assertRaises(KeyError):
                render_dataset(ROOT, REGISTRY, {'id': company, 'name': company}, self.collection['id'], record)

    def test_independent_companies_are_filtered_in_rows_sources_and_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / 'dataset'
            folder.mkdir()
            with duckdb.connect(str(folder / 'research.duckdb')) as db:
                db.execute('CREATE TABLE observations(record_id VARCHAR, entity_id VARCHAR, metric_id VARCHAR, period_end DATE, source_snapshot_id VARCHAR, payload JSON)')
                db.execute('CREATE TABLE sources(source_snapshot_id VARCHAR, company_id VARCHAR)')
                db.execute('CREATE TABLE evidence(evidence_id VARCHAR, source_snapshot_id VARCHAR, payload JSON)')
                for company in ('orchard', 'harbor'):
                    db.execute('INSERT INTO sources VALUES (?, ?)', [company + '-source', company])
                    db.execute('INSERT INTO observations VALUES (?, ?, ?, ?, ?, ?)', [company + '-row', company, 'workers', '2024-12-31', company + '-source', json.dumps({'record_id': company + '-row'})])
                    db.execute('INSERT INTO evidence VALUES (?, ?, ?)', [company + '-ev', company + '-source', json.dumps({'quote': company + ' evidence'})])
            (folder / 'sources.json').write_text(json.dumps([{'company_id': company} for company in ('orchard', 'harbor')]))
            (folder / 'metrics.json').write_text('{}')
            (folder / 'manifest.json').write_text(json.dumps({'files': {p.name: sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()}}))
            binding = {'dataset': {'path': 'dataset', 'manifest_sha256': sha256((folder / 'manifest.json').read_bytes()).hexdigest()}}
            for company in ('orchard', 'harbor', 'absent'):
                data = read_dataset(root, {**binding, 'company_id': company})
                self.assertEqual(data['records'], [] if company == 'absent' else [{'record_id': company + '-row'}])
                self.assertEqual(data['sources'], [] if company == 'absent' else [{'company_id': company}])
                self.assertEqual(set(data['evidence']), set() if company == 'absent' else {company + '-ev'})
            (folder / 'metrics.json').write_text('{"tampered":true}')
            with self.assertRaisesRegex(ValueError, 'artifact changed'):
                read_dataset(root, {**binding, 'company_id': 'orchard'})
            (folder / 'manifest.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'manifest changed'):
                read_dataset(root, {**binding, 'company_id': 'orchard'})

    def test_source_table_preserves_spans_and_escapes_text(self):
        html = render_block({'table': {'cells': [{'row': 0, 'column': 0, 'rowspan': 2, 'colspan': 3, 'text': '<script>source</script>'}]}})
        self.assertIn('colspan="3" rowspan="2"', html)
        self.assertIn('&lt;script&gt;source&lt;/script&gt;', html)
        self.assertNotIn('<script>', html)
