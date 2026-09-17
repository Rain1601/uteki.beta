import asyncio
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uteki.agents.research_archive import Store, ArchiveError
from uteki.agents.archive_rerun import run_archive_revision
from tests.unit.test_research_archive import sample


class ArchiveRerunTests(unittest.TestCase):
    def test_completed_agent_answer_is_archived_with_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'state.json')
            store.seed([sample(mode='single',answer={'claims':[{'text':'Original'}]})])
            doc=dict(id='10k-2024',form='10-K',period_end='2024-12-31',filed_at='2025-02-01')
            async def fake(root,manifest,output,question,model,mode,**kwargs):
                Path(output).mkdir()
                (Path(output)/'result.json').write_text(json.dumps({'status':'answered','answer':{'claims':[{'text':'Revised','citations':[]}]},'citation_errors':[]}))
            with patch('uteki.agents.archive_rerun.load_catalog',return_value={'documents':[doc]}), \
                 patch('uteki.agents.archive_rerun.pin_materials',return_value={'documents':[doc],'indexes':{}}), \
                 patch('uteki.agents.analysis_comparison.run_mode',side_effect=fake), \
                 patch('uteki.agents.call_costs.pricing_snapshot',return_value={}):
                result=asyncio.run(run_archive_revision(tmp,store,Path(tmp)/'run',source_id='a',
                    document_ids=['10k-2024'],question='Recheck',model='test',provider='openai'))
            rows={r['id']:r for r in store.list()}
            revised=rows[result['snapshot_id']]
            self.assertEqual(revised['parent_snapshot_id'],'a')
            self.assertEqual(revised['editor_type'],'agent')
            self.assertEqual(revised['agent_provenance']['model'],'test')
            self.assertEqual(revised['validation_status'],'pending')
            self.assertEqual(rows['a']['answer']['claims'][0]['text'],'Original')

    def test_entry_point_loads_current_notes_without_adopting(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'state.json')
            store.seed([sample(mode='single',answer={'claims':[{'text':'Check growth'}]})])
            store.annotate('a','add',0,claim_number=1,start=0,end=5,quote='Check',
                           text_hash=hashlib.sha256(b'Check growth').hexdigest(),note='Check margins too')
            doc=dict(id='10k-2024',form='10-K',period_end='2024-12-31',filed_at='2025-02-01')
            seen=[]
            async def fake(root,manifest,output,question,model,mode,**kwargs):
                seen.append(kwargs['research_context'])
                Path(output).mkdir()
                (Path(output)/'result.json').write_text(json.dumps({'status':'invalid_citations'}))
            with patch('uteki.agents.archive_rerun.load_catalog',return_value={'documents':[doc]}), \
                 patch('uteki.agents.archive_rerun.pin_materials',return_value={'documents':[doc],'indexes':{}}), \
                 patch('uteki.agents.analysis_comparison.run_mode',side_effect=fake), \
                 patch('uteki.agents.call_costs.pricing_snapshot',return_value={}):
                result=asyncio.run(run_archive_revision(tmp,store,Path(tmp)/'run',source_id='a',
                    document_ids=['10k-2024'],question='Check growth',model='test',provider='openai'))
                self.assertEqual(result['status'],'invalid_citations')
                self.assertFalse(result['automatic_adoption'])
                self.assertEqual(seen[0]['rerun_source']['opinions'][0]['text'],'Check margins too')
                self.assertFalse(seen[0]['strict'])
                self.assertEqual(store.list()[0]['status'],'candidate')
                with self.assertRaises(ArchiveError):
                    asyncio.run(run_archive_revision(tmp,store,Path(tmp)/'other',source_id='a',
                        document_ids=[],question='Check growth',model='test',provider='openai'))
