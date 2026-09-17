import json
from pathlib import Path
import tempfile
import shutil
import unittest
from lxml import html
from uteki.agents.document_reader import DocumentReader

ROOT = Path(__file__).resolve().parents[2]
FOLDER = ROOT / 'data/document_library/alphabet/sources/alphabet-000165204426000071/indexes/v0.4-candidate'


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.reader = DocumentReader(FOLDER)
        self.node = self.reader.index['index_id'] + '-part-i-item-1'

    def test_outline_has_no_body(self):
        out = self.reader.outline()
        self.assertEqual(len(out['nodes']), 12)
        self.assertNotIn('blocks', out)

    def test_search_pagination_and_empty(self):
        one = self.reader.search(self.node, 'Google Cloud', limit=1)
        two = self.reader.search(self.node, 'google cloud', offset=1, limit=1)
        self.assertEqual(one['next_offset'], 1)
        self.assertNotEqual(one['hits'], two['hits'])
        self.assertEqual(self.reader.search(self.node, 'no-such-phrase-xyz')['total'], 0)
        with self.assertRaises(ValueError):
            self.reader.search(self.node, '')

    def test_context_full_list_and_continuation(self):
        start = self.reader.search(self.node, 'Google Cloud')['hits'][0]['block_id']
        result = self.reader.read(self.node, start, 9)
        self.assertEqual(sum(b['type'] == 'list_item' for b in result['blocks']), 4)
        self.assertEqual(result['blocks'][-1]['type'], 'heading_candidate')
        self.assertIsNotNone(result['next_block_id'])

    def test_invalid_scope_and_size(self):
        with self.assertRaises(ValueError):
            self.reader.read(self.node, self.reader.blocks[-1]['block_id'])
        with self.assertRaises(ValueError):
            self.reader.read(self.node, self.reader.blocks[0]['block_id'], 100)
        with self.assertRaises(KeyError):
            self.reader.search('unknown-node', 'Cloud')

    def test_table_preserved(self):
        table = next(b for b in self.reader.blocks[52:490] if b['type'] == 'table')
        out = self.reader.read(self.node, table['block_id'], 1)
        self.assertEqual(next(b for b in out['blocks'] if b['block_id']==table['block_id'])['table'], table['table'])

    def test_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('manifest.json', 'index.json', 'blocks.jsonl'):
                shutil.copy(FOLDER / name, Path(tmp) / name)
            with (Path(tmp) / 'blocks.jsonl').open('a') as stream:
                stream.write(' ')
            with self.assertRaises(ValueError):
                DocumentReader(tmp)

    def test_demo_evidence_targets(self):
        run = ROOT / 'experiments/document_reader/d0-cloud-revenue-03'
        tree = html.parse(str(run / 'source.html'))
        result = json.loads((run / 'call-003.json').read_text())['result']
        for block in result['blocks']:
            marker = tree.xpath('//*[@id=$id]', id=block['block_id'])
            self.assertEqual(len(marker), 1)
            text = ''.join(marker[0].getnext().itertext())
            self.assertEqual(' '.join(text.split()), block['text'])
