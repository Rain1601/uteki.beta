import json
from pathlib import Path
import unittest
from uteki.agents.document_reader import DocumentReader
from uteki.agents.reading_groups import is_list_item

ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/'experiments/document_reader/multi-query-v0.2'


class ContextRegressionTests(unittest.TestCase):
    def test_cross_page_and_children(self):
        r=DocumentReader(ROOT/'data/source_documents/alphabet_2025_10k/indexes/v0.5-candidate')
        node=next(n for n in r.index['nodes'] if n['kind']=='item' and n['item_number']=='1')
        b=next(b for b in r.blocks if b['text'].startswith('•AI-optimized Infrastructure:'))
        out=r.read(node['node_id'],b['block_id'],1)
        self.assertTrue(any('Customers use Google Cloud' in b['text'] for b in out['blocks']))
        g=out['reading_groups'][0]
        self.assertEqual(sum(i['parent_id'] is not None for i in g['items']),2)

    def test_compound_not_list(self):
        self.assertFalse(is_list_item({'type':'paragraph','text':'•one•two Another Section'}))

    def test_cloud_isolated(self):
        c=json.loads((RUN/'call-019.json').read_text())
        blocks=c['result']['blocks']
        self.assertEqual(len(blocks),5)
        self.assertFalse(any('Cost of Revenues' in b['text'] for b in blocks))

    def test_all_tables_have_units(self):
        for name in ('024','025','026','027'):
            c=json.loads((RUN/f'call-{name}.json').read_text())
            self.assertTrue(any('in millions' in b['text'] for b in c['result']['blocks']))
            self.assertTrue(any(b['type']=='table' for b in c['result']['blocks']))

    def test_old_sources_and_indexes_intact(self):
        old=json.loads((ROOT/'experiments/document_reader/multi-query-v0.1/manifest.json').read_text())
        new=json.loads((RUN/'manifest.json').read_text())
        for d in old['documents']:
            r=DocumentReader(ROOT/d['index_folder'])
            self.assertEqual(r.manifest,old['indexes'][d['id']])
            self.assertEqual(r.manifest['source_sha256'],new['indexes'][d['id']]['source_sha256'])

    def test_replay_count_and_missing_material(self):
        calls=[json.loads(p.read_text()) for p in RUN.glob('call-*.json')]
        self.assertEqual(len(calls),33)
        self.assertEqual(next(c['result'] for c in calls if c['case']=='q6'),[])
