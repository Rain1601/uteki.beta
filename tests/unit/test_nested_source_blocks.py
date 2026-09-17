import gzip
import json
import unittest
from pathlib import Path
from lxml import html
from uteki.infrastructure.document_sources.sec_index import parse_sec_source

ROOT = Path(__file__).resolve().parents[2]


class NestedBlocksTests(unittest.TestCase):
    def test_container_text_before_and_after_table_is_retained(self):
        raw = b'''<html><body><ix:continuation><div>Before <span>inline</span>.</div>
        <table><tr><td>Cell</td></tr></table><div>After.</div>
        <div style="font-weight:700">Heading</div><div>&bull;List entry</div></ix:continuation></body></html>'''
        parsed = parse_sec_source('test','https://example.org',raw,form_type='10-Q')
        self.assertEqual([b.text for b in parsed.blocks],['Before inline.','Cell','After.','Heading','•List entry'])
        self.assertEqual([b.type for b in parsed.blocks],['paragraph','table','paragraph','heading_candidate','list_item'])

    def test_reported_advertising_section_boundaries(self):
        folder=ROOT/'data/document_library/alphabet/sources/alphabet-000165204426000071'
        blocks=[json.loads(l) for l in (folder/'indexes/v0.4-candidate/blocks.jsonl').read_text().splitlines()]
        start=next(i for i,b in enumerate(blocks) if b['text'].startswith('Our customers generally purchase'))
        section=blocks[start:start+11]
        self.assertEqual([b['type'] for b in section], ['paragraph']*3+['heading_candidate','paragraph']+['list_item']*4+['paragraph','heading_candidate'])
        self.assertEqual(section[3]['text'],'Google Subscriptions, Platforms, and Devices')
        self.assertEqual(section[10]['text'],'Google Cloud')
        raw=gzip.decompress((folder/'source.html.gz').read_bytes())
        tree=html.fromstring(raw).getroottree()
        for b in section:
            # lxml HTML tag names containing ':' need local-name XPath steps.
            path=b['dom_path'].replace('ix:continuation','*[name()="ix:continuation"]')
            elements=tree.xpath(path)
            self.assertEqual(len(elements),1)
            self.assertEqual(' '.join(elements[0].text_content().split()),b['text'])
