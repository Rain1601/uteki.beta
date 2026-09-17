import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from uteki.agents.research_archive import Store, ArchiveError, ConflictError
from tests.unit.test_research_archive import sample
from tests.unit.test_research_archive_routes import ArchiveRoutesTests


class ReadingAnnotationTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / 'state.json'
        self.store = Store(self.path)
        self.text = '事实：AI 😀 可能增长。AI 可能增长。'
        self.store.seed([sample(answer={'claims':[{'text':self.text}]}), sample('b',answer={'claims':[{'text':self.text}]})])
        self.request = dict(claim_number=1,start=3,end=7,quote=self.text[3:7],text_hash=hashlib.sha256(self.text.encode()).hexdigest())

    def test_round_trip_isolated_and_does_not_modify_snapshot(self):
        before = self.store.list()
        result = self.store.annotate('a','add',0,**self.request)
        self.assertEqual(result['revision'],1)
        self.assertEqual(Store(self.path).annotations('a'),result)
        self.assertEqual(self.store.annotations('b')['marks'],[])
        self.assertEqual(self.store.list(),before)
        removed = self.store.annotate('a','remove',1,annotation_id=result['marks'][0]['annotation_id'])
        self.assertEqual(removed,{'revision':2,'marks':[]})
        state = json.loads(self.path.read_text())
        self.assertIn('removed_at',state['reading_annotations']['a']['marks'][0])
        self.assertEqual(state['audit_events'][-1]['action'],'annotation_remove')

    def test_tampered_offsets_hash_quotes_and_unknown_claim_fail(self):
        for patch in ({'start':-1},{'end':999},{'quote':'invented'},{'text_hash':'wrong'}, {'claim_number':2}, {'start':True}):
            before=self.path.read_bytes()
            with self.assertRaises(ArchiveError):
                self.store.annotate('a','add',0,**(self.request|patch))
            self.assertEqual(self.path.read_bytes(),before)

    def test_conflict_and_overlapping_selection(self):
        self.store.annotate('a','add',0,**self.request)
        with self.assertRaises(ConflictError):self.store.annotate('a','add',0,**self.request)
        with self.assertRaises(ArchiveError):self.store.annotate('a','add',1,**self.request)

    def test_adopted_answer_remains_immutable_deleted_cannot_annotate(self):
        self.store.act('a','adopt',1,confirm_competitors=True)
        before=self.store.list()
        self.store.annotate('a','add',0,**self.request)
        self.assertEqual(self.store.list(),before)
        # b is archived by adoption, and can then be soft-deleted.
        self.store.act('b','delete',1)
        with self.assertRaises(ArchiveError):self.store.annotate('b','add',0,**self.request)

    def test_note_roundtrip_edit_withdraw_and_atomic_validation(self):
        before=self.path.read_bytes()
        with self.assertRaises(ArchiveError):
            self.store.annotate('a','add',0,**self.request,note=' ')
        self.assertEqual(self.path.read_bytes(),before)
        result=self.store.annotate('a','add',0,**self.request,note='核查利润率',carry_forward=True)
        mark=result['marks'][0]
        self.assertEqual(mark['note'],'核查利润率')
        comment=next(r for r in self.store.list() if r['id']=='a')['comments'][0]
        self.assertEqual(comment['source_selection']['quote'],self.request['quote'])
        self.assertTrue(comment['carry_forward'])
        updated=self.store.annotate('a','note',1,annotation_id=mark['annotation_id'],expected_note_version=1,note='比较前后年度',carry_forward=True)
        self.assertEqual(updated['marks'][0]['note_version'],2)
        self.store.annotate('a','remove',2,annotation_id=mark['annotation_id'],expected_note_version=2)
        row=next(r for r in self.store.list() if r['id']=='a')
        self.assertTrue(row['comments'][0]['withdrawn'])
        self.assertEqual(row['answer']['claims'][0]['text'],self.text)

    def test_existing_underline_can_receive_note_and_general_edits_conflict(self):
        mark=self.store.annotate('a','add',0,**self.request)['marks'][0]
        result=self.store.annotate('a','note',1,annotation_id=mark['annotation_id'],note='Review this')
        row=next(r for r in self.store.list() if r['id']=='a')
        self.store.act('a','edit_comment',row['revision'],comment_id=result['marks'][0]['comment_id'],text='Changed elsewhere')
        with self.assertRaises(ConflictError):
            self.store.annotate('a','note',2,annotation_id=mark['annotation_id'],expected_note_version=1,note='Stale')

    def test_unadopted_rerun_feedback_is_not_an_annual_baseline(self):
        from uteki.agents.research_archive_context import build_context
        self.store.annotate('a','add',0,**self.request,note='Do not assume growth',carry_forward=True)
        material=dict(id='10k-2024',form='10-K',period_end='2024-12-31',filed_at='2025-02-01')
        ctx=build_context(self.store,'alphabet','company-drivers','2099-01-01',
                          researcher_id='single-default',material=material,rerun_from='a')
        self.assertEqual(ctx['baselines'],[])
        self.assertEqual(ctx['rerun_source']['opinions'][0]['text'],'Do not assume growth')
        self.assertEqual(ctx['rerun_source']['opinions'][0]['review_status'],'pending')
        self.assertEqual(ctx['rerun_source']['role'],'draft_to_revise_not_evidence')
        self.assertIsNone(ctx['baseline_snapshot_id'])
        with self.assertRaises(ArchiveError):
            build_context(self.store,'alphabet','company-drivers','2099-01-01',
                          researcher_id='team-a',material=material,rerun_from='a')
        with self.assertRaises(ArchiveError):
            build_context(self.store,'alphabet','company-drivers','2025-01-01',
                          researcher_id='single-default',material=material,rerun_from='a')


class AnnotationRoutesTests(ArchiveRoutesTests):
    def test_annotation_route_security_and_reload(self):
        row=json.loads(self.request('/api/research-archive')[1])['snapshots'][0]
        text=row['answer']['claims'][0]['text']
        data=dict(snapshot_id=row['id'],action='add',expected_revision=0,claim_number=1,start=0,end=2,quote=text[:2],text_hash=hashlib.sha256(text.encode()).hexdigest())
        self.assertEqual(self.request('/api/research-annotations',data,{'Origin':'https://evil.example'})[0],403)
        status,body=self.request('/api/research-annotations',data)
        self.assertEqual(status,200)
        status,reloaded=self.request('/api/research-annotations?snapshot_id='+row['id'])
        self.assertEqual(json.loads(body),json.loads(reloaded))
        self.assertEqual(self.request('/api/research-annotations',data)[0],409)
        updated=json.loads(self.request('/api/research-archive')[1])['snapshots'][0]
        self.assertEqual(updated,row)
