from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from uteki.agents.research_archive import Store, ArchiveError, ConflictError
from uteki.agents.research_archive_context import build_context, read_history
from tests.unit.test_research_archive import sample
from apps.review_workbench.research_archive_ui import render_archive


class ResearcherStreamsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'state.json'
        self.store = Store(self.path)
        self.store.seed([sample('a'), sample('b'), sample('team', researcher_id='team-a')])

    def row(self, identifier):
        return next(r for r in self.store.list() if r['id']==identifier)

    def replace(self, identifier, old):
        new, previous = self.row(identifier), self.row(old)
        return self.store.act(identifier,'adopt',new['revision'], expected_slot_revision=new['slot_revision'],
                              replace_snapshot_id=old, replace_revision=previous['revision'])

    def test_independent_slots_and_context(self):
        self.store.act('a','adopt',1)
        self.store.act('team','adopt',1)
        self.assertEqual(sum(r['status']=='adopted' for r in self.store.list()),2)
        with self.assertRaises(ArchiveError):
            self.store.context('alphabet','company-drivers','2099-01-01')
        for researcher, expected in [('single-default','a'),('team-a','team')]:
            c=build_context(self.store,'alphabet','company-drivers','2099-01-01',researcher_id=researcher)
            self.assertEqual(c['baseline_snapshot_id'],expected)
            self.assertEqual(c['baseline']['content']['researcher_id'],researcher)

    def test_replace_is_atomic_keeps_other_candidates(self):
        self.store.seed([sample('c')])
        self.store.act('a','adopt',1)
        before=self.path.read_bytes()
        with self.assertRaises(ConflictError):
            self.store.act('b','adopt',1)
        self.assertEqual(before,self.path.read_bytes())
        self.replace('b','a')
        self.assertEqual(self.row('a')['status'],'archived')
        self.assertEqual(self.row('b')['status'],'adopted')
        self.assertEqual(self.row('c')['status'],'candidate')

    def test_stale_slot_after_adopt_archive_cycle_rejected(self):
        token=self.row('b')['slot_revision']
        self.store.act('a','adopt',1)
        self.store.act('a','archive',2)
        with self.assertRaises(ConflictError):
            self.store.act('b','adopt',1,expected_slot_revision=token)

    def test_two_replacements_only_one_wins(self):
        self.store.seed([sample('c')]); self.store.act('a','adopt',1)
        token=self.row('b')['slot_revision']
        def adopt(key):
            try:
                self.store.act(key,'adopt',1,expected_slot_revision=token,replace_snapshot_id='a',replace_revision=2)
                return True
            except ConflictError: return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sum(pool.map(adopt,['b','c'])),1)

    def test_reject_reconsider_and_failed_candidate(self):
        self.store.act('a','adopt',1)
        self.store.act('b','reject',1,reason='Unsupported mechanism')
        with self.assertRaises(ArchiveError): self.store.act('b','adopt',2)
        self.store.act('b','reconsider',2)
        self.assertEqual(self.row('b')['status'],'candidate')
        self.store.seed([sample('bad',validation_status='failed')])
        with self.assertRaises(ArchiveError): self.replace('bad','a')
        self.assertEqual(self.row('a')['status'],'adopted')

    def test_replacement_flags_descendants_without_changing_frozen_input(self):
        self.store.act('a','adopt',1)
        self.store.seed([sample('later',primary_document_id='q2',material_available_at='2025-05-01',
            knowledge_cutoff_at='2025-05-01',baseline_snapshot_id='a')])
        self.store.act('later','adopt',1)
        frozen=build_context(self.store,'alphabet','company-drivers','2099-01-01',researcher_id='single-default')
        original=deepcopy(frozen)
        self.replace('b','a')
        self.assertEqual(frozen,original)
        self.assertEqual(self.row('later')['status'],'adopted')
        self.assertTrue(self.row('later')['inheritance_review_required'])
        with self.assertRaises(ArchiveError): read_history(frozen,self.store,'a')
        c=build_context(self.store,'alphabet','company-drivers','2099-01-01',researcher_id='single-default')
        self.assertTrue(c['inheritance_notices'])

    def test_foreign_opinion_and_history_are_excluded(self):
        self.store.act('team','adopt',1)
        comment=self.store.act('team','comment',2,text='Team view',carry_forward=True)['snapshot']['comments'][0]
        self.store.seed([sample('new',primary_document_id='q2',inherited_comment_refs=[{'comment_id':comment['comment_id']}])])
        self.store.act('new','adopt',1)
        c=build_context(self.store,'alphabet','company-drivers','2099-01-01',researcher_id='single-default')
        self.assertEqual(c['opinions'],[])
        with self.assertRaises(ArchiveError): read_history(c,self.store,'team')

    def test_edit_from_effective_preserves_run_and_evidence(self):
        answer={'claims':[{'text':'Old hypothesis','citations':[{'block_id':'x','quote':'source'}]}], 'limitations':['unknown'],'findings':[]}
        self.store.seed([sample('text',primary_document_id='other',answer=answer)])
        self.store.act('text','adopt',1)
        changed=deepcopy(answer);changed['claims'][0]['text']='New hypothesis'
        revision=self.store.act('text','edit',2,answer=changed,human_notes='Reason')['snapshot']
        self.assertEqual(self.row('text')['answer'],answer)
        self.assertEqual(self.row('text')['status'],'adopted')
        self.assertEqual(revision['run_started_at'],self.row('text')['run_started_at'])
        self.assertEqual(revision['validation_status'],'pending')
        self.assertIn('answer',revision['edit_diff'])
        changed['claims'][0]['citations'][0]['quote']='fabricated'
        with self.assertRaises(ArchiveError): self.store.act('text','edit',3,answer=changed)

    def test_migration_dry_run_backup_idempotence_and_unassigned(self):
        # Simulate legacy rows, preserving all non-identity state verbatim.
        with self.store._transaction(write=True) as state:
            for row in state['snapshots'].values(): row.pop('researcher_id')
        before=self.path.read_bytes()
        mapping={'a':{'researcher_id':'single-default'},'team':{'researcher_id':'team-a'}}
        self.store.migrate_researchers(mapping)
        self.assertEqual(before,self.path.read_bytes())
        report=self.store.migrate_researchers(mapping,dry_run=False)
        self.assertEqual(Path(report['backup']).read_bytes(),before)
        self.assertEqual(self.row('b')['researcher_id'],'unassigned')
        with self.assertRaises(ArchiveError): self.store.act('b','adopt',1)
        saved=self.path.read_bytes();self.store.migrate_researchers(mapping,dry_run=False)
        self.assertEqual(saved,self.path.read_bytes())

    def test_ui_filters_and_one_material_entry(self):
        self.store.act('a','adopt',1)
        page=render_archive({'id':'alphabet'},self.store.list(),researcher_id='single-default')
        from lxml import html
        dom=html.fromstring(page)
        self.assertEqual(len(dom.xpath('//aside/a[contains(@class,"agent-entry")]')),2)
        self.assertEqual(len(dom.xpath('//div[@class="material-list"]//a[@class="material-row"]')),1)
        self.assertIn('snapshot=a',dom.xpath('//div[@class="material-list"]//a[@class="material-row"]/@href')[0])
        self.assertNotIn('snapshot=team',page)
        self.assertNotIn('researcher-filter',page)
        self.assertIn('Context policy for future analyses',page)
        foreign=render_archive({'id':'alphabet'},self.store.list(),'team',researcher_id='single-default')
        self.assertIn('does not belong',foreign)

    def test_migration_conflict_does_not_write(self):
        self.store.act('a','adopt',1)
        self.store.act('team','adopt',1)
        with self.store._transaction(write=True) as state:
            for row in state['snapshots'].values(): row.pop('researcher_id')
        before=self.path.read_bytes()
        mapping={key:{'researcher_id':'same-team'} for key in ('a','team')}
        with self.assertRaises(ConflictError): self.store.migrate_researchers(mapping,dry_run=False)
        self.assertEqual(self.path.read_bytes(),before)

    def test_migration_preserves_comments_underlines_and_payload(self):
        self.store.act('a','comment',1,text='Keep this review')
        with self.store._transaction(write=True) as state:
            state['reading_annotations']={'a':{'revision':1,'marks':[{'quote':'original'}]}}
            for row in state['snapshots'].values(): row.pop('researcher_id')
        before=json.loads(self.path.read_text())
        self.store.migrate_researchers({'a':{'researcher_id':'single-default'}},dry_run=False)
        after=json.loads(self.path.read_text())
        for key in ('comments','reading_annotations'): self.assertEqual(before[key],after[key])
        self.assertEqual(after['audit_events'][:-1],before['audit_events'])
        for key,row in before['snapshots'].items():
            for field,value in row.items(): self.assertEqual(after['snapshots'][key][field],value)
