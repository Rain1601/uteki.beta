import tempfile
import unittest
from pathlib import Path
from uteki.agents.research_archive import Store,ArchiveError,ConflictError
from uteki.agents.review_blocks import review_blocks
from tests.unit.test_research_archive import sample

class BlockStructureTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=Store(Path(self.tmp.name)/'state.json')
        self.answer={'claims':[{'text':'Original','citations':[{'quote':'source'}]},{'text':'Second','citations':[]}]}
        self.store.seed([sample(answer=self.answer)])

    def test_insert_preserves_citations_and_moves_acceptance(self):
        self.store.act('a','accept_block',1,block_id='claim:1',block_hash=review_blocks(self.answer)['claim:1'])
        row=self.store.act('a','insert_block',2,block_index=1,block_kind='inference',text='My inference')['snapshot']
        self.assertEqual(row['answer']['claims'][0],self.answer['claims'][0])
        self.assertEqual(row['answer']['claims'][1],{'kind':'inference','text':'My inference','citations':[]})
        self.assertTrue(row['block_decisions']['claim:2']['accepted'])
        self.assertNotIn('claim:1',row['block_decisions'])
        self.assertEqual(row['validation_status'],'pending')
        self.assertEqual(row['edit_diff']['answer']['before'],self.answer)

    def test_delete_is_revision_not_original_mutation(self):
        row=self.store.act('a','delete_block',1,block_index=0)['snapshot']
        self.assertEqual(row['answer']['claims'],self.answer['claims'][1:])
        original=next(x for x in self.store.list() if x['id']=='a')
        self.assertEqual(original['answer'],self.answer)
        with self.assertRaises(ConflictError):self.store.act('a','delete_block',1,block_index=0)

    def test_invalid_insert_and_delete_rejected(self):
        for kw in [dict(block_index=-1,block_kind='fact',text='x'),dict(block_index=0,block_kind='unknown',text='x'),dict(block_index=0,block_kind='fact',text=' ')]:
            with self.assertRaises(ArchiveError):self.store.act('a','insert_block',1,**kw)
        with self.assertRaises(ArchiveError):self.store.act('a','delete_block',1,block_index=2)

    def test_markdown_insert_and_table_deletion(self):
        self.store.seed([sample(id='md',answer={'report_markdown':'# Title\n|A|B|\n|---|---|\n|1|2|'})])
        row=self.store.act('md','delete_block',1,block_index=1,block_count=3)['snapshot']
        self.assertEqual(row['answer']['report_markdown'],'# Title')
        new=self.store.act(row['id'],'insert_block',1,block_index=1,block_kind='question',text='Why?')['snapshot']
        self.assertIn('待验证问题：Why?',new['answer']['report_markdown'])
