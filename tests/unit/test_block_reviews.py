import tempfile
import unittest
from pathlib import Path
from uteki.agents.research_archive import Store, ConflictError, ArchiveError
from uteki.agents.review_blocks import review_blocks
from tests.unit.test_research_archive import sample

class BlockReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'state.json';self.store=Store(self.path)
        self.answer={'report_markdown':'# Title\n\nFirst\nSecond'}
        self.store.seed([sample(answer=self.answer)])

    def accept(self,key,revision):
        return self.store.act('a','accept_block',revision,block_id=key,block_hash=review_blocks(self.answer)[key])['snapshot']

    def test_persistence_conflict_undo_and_no_global_adoption(self):
        self.accept('md:2',1)
        row=Store(self.path).list()[0]
        self.assertTrue(row['block_decisions']['md:2']['accepted'])
        self.assertEqual(row['status'],'candidate')
        self.assertEqual(row['block_review_events'][0]['actor'],'user')
        with self.assertRaises(ConflictError):self.accept('md:3',1)
        undone=self.store.act('a','unaccept_block',2,block_id='md:2',block_hash=review_blocks(self.answer)['md:2'])['snapshot']
        self.assertFalse(undone['block_decisions']['md:2']['accepted'])
        self.assertEqual(len(undone['block_review_events']),2)

    def test_edit_invalidates_only_changed_blocks(self):
        self.accept('md:2',1);self.accept('md:3',2)
        new=self.store.act('a','edit',3,answer={'report_markdown':'# Title\n\nChanged\nSecond'},human_notes='Correction')['snapshot']
        self.assertNotIn('md:2',new['block_decisions'])
        self.assertTrue(new['block_decisions']['md:3']['accepted'])
        original=next(r for r in Store(self.path).list() if r['id']=='a')
        self.assertTrue(original['block_decisions']['md:2']['accepted'])

    def test_bad_hash_rejected_and_citations_bound(self):
        with self.assertRaises(ConflictError):self.store.act('a','accept_block',1,block_id='md:2',block_hash='wrong')
        a={'claims':[{'text':'same','citations':[{'quote':'old'}]}]}
        b={'claims':[{'text':'same','citations':[{'quote':'new'}]}]}
        self.assertNotEqual(review_blocks(a),review_blocks(b))

    def test_table_units_match_renderer(self):
        blocks=review_blocks({'report_markdown':'| A | B |\n|---|---|\n| 1 | 2 |'})
        self.assertEqual(set(blocks),{'md:0:0','md:0:1','md:2:0','md:2:1'})
