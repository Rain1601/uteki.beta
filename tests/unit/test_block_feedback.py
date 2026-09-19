import tempfile
import unittest
from pathlib import Path
from uteki.agents.research_archive import Store, ConflictError, ArchiveError
from uteki.agents.review_blocks import review_blocks
from uteki.agents.research_archive_context import _rerun_feedback
from tests.unit.test_research_archive import sample

class BlockFeedbackTests(unittest.TestCase):
    def test_feedback_persists_and_enters_matching_rerun(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'state.json')
            row=sample(answer={'claims':[{'text':'Source paragraph','citations':[]}]})
            store.seed([row]);key='claim:0';digest=review_blocks(row['answer'])[key]
            result=store.act('a','comment',1,feedback_vote='down',block_id=key,block_hash=digest,text='Need evidence, not a list of assertions',kind='preference',carry_forward=True)
            saved=Store(store.path).list()[0]['comments'][0]
            self.assertEqual(saved['feedback_vote'],'down')
            self.assertEqual(saved['block_hash'],digest)
            self.assertEqual(saved['source_answer'],row['answer'])
            self.assertEqual(saved['policy_status'],'feedback_not_adopted_rule')
            import json
            state=json.loads(store.path.read_text());source=state['snapshots']['a']
            ctx={'company_id':source['company_id'],'scope':source['scope'],'researcher_id':source.get('researcher_id'), 'current_material':{'id':source['primary_document_id']},'cutoff':'2099-01-01T00:00:00Z','strict':False}
            carried=_rerun_feedback(state,ctx,'a')['opinions'][0]
            self.assertEqual(carried['block_id'],key)
            self.assertTrue(carried['review_required'])
            with self.assertRaises(ConflictError):store.act('a','comment',2,feedback_vote='down',block_id=key,block_hash='stale',text='reason')
            with self.assertRaises(ArchiveError):store.act('a','comment',2,feedback_vote='down',block_id=key,block_hash=digest,text=' ')
