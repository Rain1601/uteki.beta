import json
import unittest
from pathlib import Path
from apps.review_workbench.company_data import render_company_data, render_document_status
from apps.review_workbench.document_library import index_url, resolve_index

ROOT = Path(__file__).resolve().parents[2]


class CompanyDataTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads((ROOT / 'data/document_library/alphabet/catalog.json').read_text())
        self.company = {'id':'alphabet','name':'Alphabet','ticker':'GOOGL'}

    def test_all_discovered_documents_have_distinct_links(self):
        page = render_company_data(self.company, self.catalog)
        ids = [d['id'] for d in self.catalog['documents']]
        self.assertEqual(len(ids), len(set(ids)))
        for doc in self.catalog['documents']:
            self.assertIn(index_url(doc) if doc.get('index_folder') else '/documents/' + doc['id'], page)

    def test_three_layers_and_reviewed_run(self):
        page = render_company_data(self.company, self.catalog, True)
        for section in ('materials','structure','semantic'):
            self.assertIn(f'id="{section}"', page)
        self.assertIn('run-9856300a8d74fa77', page)

    def test_unavailable_not_redirected_to_wrong_index(self):
        doc = dict(self.catalog['documents'][0], status='download_failed', error='HTTP 403')
        page = render_document_status(doc)
        self.assertIn(doc['source_url'], page)
        self.assertNotIn('href="/document-index"', page)

    def test_company_is_escaped(self):
        page = render_company_data({'id':'other','name':'<script>','ticker':'X'}, {})
        self.assertIn('&lt;script&gt;', page)

    def test_explicit_versions_and_traversal(self):
        for doc in self.catalog['documents']:
            resolved = resolve_index(index_url(doc), self.catalog, ROOT)
            self.assertEqual(resolved[0]['id'], doc['id'])
        self.assertIsNone(resolve_index('/companies/alphabet/documents/unknown/indexes/v0.1', self.catalog, ROOT))
        self.assertIsNone(resolve_index(index_url(self.catalog['documents'][0]).rsplit('/',1)[0]+'/v999', self.catalog, ROOT))
