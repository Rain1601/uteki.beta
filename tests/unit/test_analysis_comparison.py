import asyncio
from dataclasses import dataclass
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HAS_SDK=importlib.util.find_spec('agents') is not None
if HAS_SDK:
    from uteki.agents.analysis_comparison import ToolSession, Answer, Claim, Citation, run_mode

ROOT=Path(__file__).resolve().parents[2]


@unittest.skipUnless(HAS_SDK,'Install analysis extra for SDK tests')
class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name)
        self.manifest=json.loads((ROOT/'experiments/document_reader/multi-query-v0.2/manifest.json').read_text())
        self.session=ToolSession(ROOT,self.manifest,self.folder)

    def test_tools_schemas(self):
        tools=self.session.tools('analyst')
        self.assertEqual([t.name for t in tools],['documents','outline','search','read'])
        for tool in tools:
            self.assertIn('reason',tool.params_json_schema['properties'])

    def test_inventory_missing(self):
        self.assertEqual(self.session.call('analyst','documents','Check transcript',form='earnings_call_transcript'),[])

    def test_quote_guard_and_stage_isolation(self):
        c=Citation(document_id='d',index_id='i',block_id='b',quote='hello')
        answer=Answer(status='answered',claims=[Claim(text='claim',citations=[c])],limitations=[],findings=[],stop_reason='done')
        self.session.evidence[('d','i','b')]='hello world'
        self.session.calls=1
        self.assertEqual(self.session.validate(answer),[])
        self.assertTrue(self.session.validate(answer,stage='reviewer'))
        c.quote='fabricated'
        self.assertTrue(self.session.validate(answer))

    def test_unknown_and_budget(self):
        out=self.session.call('analyst','outline','test',document_id='unknown')
        self.assertIn('error',out)
        self.session.max_calls=1
        with self.assertRaises(RuntimeError):self.session.call('analyst','documents','test',form='')

    def test_separate_ledgers(self):
        other=ToolSession(ROOT,self.manifest,self.folder)
        self.session.evidence[('d','i','b')]='text'
        self.assertEqual(other.evidence,{})

    def test_source_compilation_requires_read(self):
        a=Answer(status='answered',claims=[Claim(text='claim',citations=[Citation(document_id='d',index_id='i',block_id='b',quote='invented')])],limitations=[],findings=[],stop_reason='done')
        self.session.evidence[('d','i','b')]='Original table 2024 2025'
        self.session.calls=1
        compiled=self.session.resolve_citations(a)
        self.assertEqual(compiled.claims[0].citations[0].quote,'Original table 2024 2025')
        self.assertEqual(a.claims[0].citations[0].quote,'invented')
        self.assertTrue(self.session.validate(self.session.resolve_citations(a,stage='reviewer'),stage='reviewer'))

    def test_budget_failure_is_recorded(self):
        self.session.max_calls=0
        with self.assertRaises(RuntimeError):
            self.session.call('analyst','documents','test',form='')
        record=json.loads((self.folder/'tool-001.json').read_text())
        self.assertEqual(record['result']['error'],'budget_exhausted')

    def test_unexpected_tool_failure_is_recorded(self):
        with patch.object(self.session,'reader',side_effect=TypeError('private detail')):
            result=self.session.call('analyst','outline','test',document_id='d')
        self.assertEqual(result['error'],'TypeError')
        self.assertNotIn('private detail',json.dumps(result))
        self.assertTrue((self.folder/'tool-001.json').exists())

    def test_orchestration_offline(self):
        @dataclass
        class Usage:
            input_tokens:int=10
            output_tokens:int=5
        names=[]
        async def fake(agent,input,**kw):
            names.append(agent.name)
            self.assertNotIn('single answer secret',input)
            return SimpleNamespace(final_output=Answer(status='insufficient_material',claims=[],limitations=['test'],findings=[],stop_reason='test'),context_wrapper=SimpleNamespace(usage=Usage()))
        with patch('uteki.agents.analysis_comparison.Runner.run',side_effect=fake):
            asyncio.run(run_mode(ROOT,self.manifest,self.folder/'single','question','test-model','single'))
            asyncio.run(run_mode(ROOT,self.manifest,self.folder/'team','question','test-model','team'))
        self.assertEqual(names,['analyst','analyst','reviewer','analyst_revision'])
        self.assertTrue((self.folder/'team/reviewer-input.json').exists())
        r=json.loads((self.folder/'single/result.json').read_text())
        self.assertEqual(r['status'],'invalid_citations') # no real tools used by mock

    def test_failure_is_explicit(self):
        async def fail(*a,**kw):raise TimeoutError('not logged')
        with patch('uteki.agents.analysis_comparison.Runner.run',side_effect=fail):
            asyncio.run(run_mode(ROOT,self.manifest,self.folder/'failed','q','test-model','single'))
        self.assertTrue((self.folder/'failed/failure.json').exists())
        self.assertFalse((self.folder/'failed/result.json').exists())

    def test_rerun_context_is_frozen_and_passed_to_every_stage_offline(self):
        @dataclass
        class Usage:
            input_tokens:int=10
            output_tokens:int=5
        context={'schema_version':'1.2','context_id':'context-test','cutoff':'2099-01-01',
                 'current_material':{'id':self.manifest['documents'][0]['id']},
                 'rerun_source':{'opinions':[{'comment_id':'review-1','text':'Verify margins, not just growth'}]}}
        manifest={**self.manifest,'material_cutoff':'2099-01-01'}
        seen=[]
        async def fake(agent,input,**kwargs):
            seen.append(agent.name)
            self.assertIn('Verify margins, not just growth',input)
            self.assertIn('NOT evidence',agent.instructions)
            return SimpleNamespace(final_output=Answer(status='insufficient_material',claims=[],limitations=[],findings=[],stop_reason='test'),context_wrapper=SimpleNamespace(usage=Usage()))
        with patch('uteki.agents.analysis_comparison.Runner.run',side_effect=fake):
            asyncio.run(run_mode(ROOT,manifest,self.folder/'with-notes','q','test-model','team',research_context=context))
        self.assertEqual(seen,['analyst','reviewer','analyst_revision'])
        self.assertEqual(json.loads((self.folder/'with-notes/context_manifest.json').read_text()),context)
        with self.assertRaises(ValueError):
            asyncio.run(run_mode(ROOT,self.manifest,self.folder/'invalid-cutoff','q','test-model','single',research_context=context))
