import unittest
from pathlib import Path
from uteki.agents.document_reader import DocumentReader
from uteki.agents.reading_groups import build_reading_groups

ROOT = Path(__file__).resolve().parents[2]


class ReadingGroupsTests(unittest.TestCase):
    def test_competition_list_is_complete(self):
        r = DocumentReader(ROOT / 'data/source_documents/alphabet_2025_10k/indexes/v0.1')
        b = r.blocks[116]
        node = next(n for n in r.index['nodes'] if n['kind'] == 'item' and n['item_number'] == '1')
        result = r.read(node['node_id'], b['block_id'], count=1)
        self.assertEqual([x['ordinal'] for x in result['blocks']], list(range(110,123)))
        self.assertEqual(len(result['reading_groups'][0]['item_ids']), 11)
        self.assertEqual(r.blocks[116]['type'], 'paragraph')

    def test_boundary_and_cross_page(self):
        blocks = [{'block_id':str(i),'type':t,'text':text} for i,(t,text) in enumerate([
            ('paragraph','Examples:'),('list_item','•one'),('page_marker','6'),
            ('list_item','•two'),('heading_candidate','Next'),('list_item','•three')])]
        groups = build_reading_groups(blocks, [])
        self.assertEqual(groups[0]['block_ids'], ['0','1','2','3'])
        groups = build_reading_groups(blocks, [{'kind':'item','start_block_id':'3'}])
        self.assertEqual(groups[0]['block_ids'], ['0','1'])
        self.assertNotIn('0',groups[1]['block_ids'])

    def test_no_merge_unrelated_prose(self):
        blocks=[{'block_id':'a','type':'paragraph','text':'Unrelated.'},
                {'block_id':'b','type':'paragraph','text':'•example'}]
        self.assertEqual(build_reading_groups(blocks,[])[0]['block_ids'], ['b'])
