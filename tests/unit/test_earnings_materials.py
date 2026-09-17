import gzip
import io
import json
from pathlib import Path
import tempfile
import unittest
from lxml import etree, html

from uteki.agents.document_reader import DocumentReader
from uteki.agents.material_library import load_catalog, pin_materials
from uteki.infrastructure.document_sources.earnings import parse_transcript_xml, digest
from apps.review_workbench.document_library import index_url, resolve_index
from apps.review_workbench.earnings_reader import render_transcript

ROOT=Path(__file__).resolve().parents[2]
CALL='alphabet-2025q4-call'
RELEASE='alphabet-2025q4-release'


class EarningsTests(unittest.TestCase):
    def setUp(self):
        self.docs={d['id']:d for d in load_catalog(ROOT)['documents']}
        self.doc=self.docs[CALL]
        self.source=ROOT/self.doc['folder']
        self.reader=DocumentReader(ROOT/self.doc['index_folder'])

    def test_catalog_additive_and_hashes(self):
        original=json.loads((ROOT/'data/document_library/alphabet/catalog.json').read_text())
        self.assertEqual(len(original['documents']),18)
        self.assertEqual(len(self.docs),20)
        for d in original['documents']:
            self.assertEqual(d,self.docs[d['id']])
        self.assertEqual(digest((self.source/'source.pdf').read_bytes()),self.doc['sha256'])

    def test_transcript_complete_deterministic_and_boxes(self):
        xml=(self.source/'layout.xml').read_bytes()
        blocks,diagnostics=parse_transcript_xml(xml)
        self.assertEqual(blocks,self.reader.blocks)
        self.assertEqual((blocks,diagnostics),parse_transcript_xml(xml))
        tree=etree.fromstring(xml)
        source_words=tree.findall('.//{*}word')
        self.assertEqual(' '.join(w.text or '' for w in source_words),' '.join(b['text'] for b in blocks))
        self.assertEqual({b['pdf_page'] for b in blocks},set(range(1,26)))
        self.assertEqual(len([n for n in self.reader.nodes.values() if n['kind']=='exchange']),9)
        for b in blocks:
            x,y,x2,y2=b['bbox'];w,h=b['page_size']
            self.assertTrue(0<=x<x2<=w and 0<=y<y2<=h)
        with self.assertRaises(ValueError):
            parse_transcript_xml(b'<doc><page/></doc>')

    def test_qa_full_context_from_answer(self):
        for n in self.reader.nodes.values():
            if n['kind']!='exchange': continue
            lo,hi=self.reader._range(n['node_id'])
            answer=next(b for b in self.reader.blocks[lo:hi] if b['speaker_role']=='management')
            result=self.reader.read('document',answer['block_id'],1)
            ids={b['block_id'] for b in result['blocks']}
            self.assertTrue({b['block_id'] for b in self.reader.blocks[lo:hi]}.issubset(ids))
            self.assertTrue(any(b['speaker_role']=='analyst' for b in result['blocks']))

    def test_prepared_remarks_load_progressively(self):
        block=next(b for b in self.reader.blocks if b['section']=='prepared' and 'Cloud significantly' in b['text'])
        result=self.reader.read('document',block['block_id'],1)
        self.assertEqual(len(result['blocks']),1)
        self.assertIn('Sundar',result['blocks'][0]['speaker'])

    def test_release_tables_and_dom(self):
        doc=self.docs[RELEASE];source=ROOT/doc['folder']
        reader=DocumentReader(ROOT/doc['index_folder'])
        raw=gzip.decompress((source/'source.html.gz').read_bytes())
        tree=html.document_fromstring(raw)
        self.assertEqual(len(tree.xpath('//table')),15)
        self.assertEqual(sum(b['type']=='table' for b in reader.blocks),15)
        for b in reader.blocks:
            self.assertTrue(tree.xpath(b['dom_path']))
            if b['type']!='page_marker': self.assertIsNone(b['reported_page'])

    def test_cutoff_and_pinning(self):
        with self.assertRaises(ValueError): pin_materials(ROOT,'2026-02-03',[CALL])
        m=pin_materials(ROOT,'2026-02-04',[CALL,RELEASE])
        self.assertEqual(len(m['documents']),2)
        self.assertIn('not a blind',m['availability_caveat'])
        with self.assertRaises(ValueError): pin_materials(ROOT,'2026-02-04',['alphabet-000165204426000018'])

    def test_tool_session_reads_new_materials_and_records(self):
        from uteki.agents.analysis_comparison import ToolSession
        with tempfile.TemporaryDirectory() as temp:
            m=pin_materials(ROOT,'2026-02-05',[CALL,RELEASE,'alphabet-000165204426000018'])
            session=ToolSession(ROOT,m,temp)
            inventory=session.call('analyst','documents','Inspect available calls',form='EARNINGS_CALL')
            self.assertEqual([d['id'] for d in inventory],[CALL])
            result=session.call('analyst','search','Locate Cloud',document_id=CALL,node_id='document',query='Cloud',limit=2)
            result=session.call('analyst','read','Read context',document_id=CALL,node_id='document',start_block_id=result['hits'][0]['block_id'],count=1)
            self.assertNotIn('error',result)
            self.assertTrue(session.evidence)
            self.assertEqual(len(list(Path(temp).glob('tool-*.json'))),3)
            m['material_cutoff']='2026-02-03'
            fresh=ToolSession(ROOT,m,temp)
            fresh.calls=3
            self.assertIn('error',fresh.call('analyst','outline','Check cutoff',document_id=CALL))

    def test_routes_and_reader(self):
        from apps.review_workbench.app import make_handler,DEFAULT_DATA
        with tempfile.TemporaryDirectory() as temp:
            handler=make_handler(DEFAULT_DATA,Path(temp)/'state.json')
            for path in [index_url(self.doc),index_url(self.doc)+'/source',index_url(self.doc)+'/original',
                         index_url(self.docs[RELEASE]),index_url(self.docs[RELEASE])+'/source',
                         index_url(self.doc)+'/assets/page-14.jpg','/companies/alphabet/materials']:
                request=object.__new__(handler);request.path=path;request.wfile=io.BytesIO()
                result={};request.send_response=lambda s:result.update(status=s)
                request.send_header=lambda *args:None;request.end_headers=lambda:None
                request.send_error=lambda s,*args:result.update(status=s)
                request.do_GET()
                self.assertEqual(result['status'],200,path)
            self.assertIsNone(resolve_index('/companies/alphabet/documents/no/indexes/v0.1',load_catalog(ROOT),ROOT))


if __name__=='__main__': unittest.main()
