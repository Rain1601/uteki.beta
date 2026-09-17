import gzip
import hashlib
import json
import unittest
from pathlib import Path
from lxml import html
from apps.review_workbench.document_index import render_document_index_page
from apps.review_workbench.document_library import index_url

ROOT = Path(__file__).resolve().parents[2]


class FilingLibraryTests(unittest.TestCase):
    def test_acquired_filings_and_node_ranges(self):
        catalog = json.loads((ROOT / 'data/document_library/alphabet/catalog.json').read_text())
        self.assertEqual(len(catalog['documents']), 18)
        for doc in catalog['documents']:
            with self.subTest(document=doc['id']):
                source = ROOT / doc['folder']
                folder = ROOT / doc['index_folder']
                manifest = json.loads((source / 'manifest.json').read_text())
                raw = gzip.decompress((source / 'source.html.gz').read_bytes())
                self.assertEqual(hashlib.sha256(raw).hexdigest(), manifest['content_sha256'])
                index = json.loads((folder / 'index.json').read_text())
                blocks = [json.loads(line) for line in (folder / 'blocks.jsonl').read_text().splitlines()]
                by_id = {b['block_id']:b for b in blocks}
                tree = html.fromstring(raw)
                self.assertEqual(len(tree.xpath('//table')), sum(b['type']=='table' for b in blocks))
                self.assertEqual(len(tree.xpath('//img')), sum(b['type']=='image' for b in blocks))
                nodes = {n['node_id']:n for n in index['nodes']}
                self.assertEqual(len(nodes), len(index['nodes']))
                self.assertEqual(sum(n['kind']=='part' for n in nodes.values()), 4 if doc['form']=='10-K' else 2)
                for n in nodes.values():
                    start, end = by_id[n['start_block_id']]['ordinal'], by_id[n['end_block_id']]['ordinal']
                    self.assertLessEqual(start,end)
                    if n['parent_id']:
                        parent=nodes[n['parent_id']]
                        self.assertGreaterEqual(start,by_id[parent['start_block_id']]['ordinal'])
                        self.assertLessEqual(end,by_id[parent['end_block_id']]['ordinal'])
                    if n['source_anchor']:
                        self.assertTrue(tree.xpath('//*[@id=$anchor]',anchor=n['source_anchor']))
                page = render_document_index_page(index,blocks,json.loads((folder/'assets.json').read_text()),doc['source_url'],title=doc['title'],source_path=index_url(doc)+'/source',asset_prefix=index_url(doc)+'/assets/')
                self.assertIn(index_url(doc)+'/source',page)
                self.assertIn(doc['title'],page)
