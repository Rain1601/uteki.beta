"""Real SDK and query loop over mocked HTTP; no paid requests."""
import asyncio
import json
from pathlib import Path
import tempfile
import unittest

import httpx2 as httpx
from openai import AsyncOpenAI

from uteki.agents.call_costs import MeteredModel, pricing_snapshot, summarize
from uteki.agents.data_query_agent import DataQueryAgent
from uteki.agents.data_query_model import SdkQueryPlanner
from uteki.agents.deepseek_model import DeepSeekChatCompletionsModel
from uteki.agents.run_budget import RunBudget
from tests.unit import test_query_scope


class QueryModelTests(unittest.TestCase):
    def test_wire_plan_tool_result_finish_and_metering(self):
        fixture = test_query_scope.QueryScopeTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        requests = []
        request = {'question': 'Calculate Acme Services operating margin for 2031 Q2.', 'company_ids': ['acme'],
                   'snapshot_id': fixture.port.snapshot_id, 'source_policy_id': 'local-frozen-v1',
                   'knowledge_cutoff': '2031-07-21', 'include_candidates': True}

        def respond(http_request):
            body = json.loads(http_request.content)
            requests.append(body)
            packet = json.loads(body['messages'][-1]['content'])
            if not packet['history']:
                decision = {'action': 'query', 'plan': {'calculations': [{'formula_id': 'operating_margin',
                    'entity_id': 'acme-services', 'periods': [{'kind': 'quarter', 'start': '2031-04-01', 'end': '2031-06-30'}]}]}}
            else:
                value = packet['history'][-1]['result']
                decision = {'action': 'finish', 'answer_parts': [{'requested_information': 'Operating margin',
                    'computed_ids': [c['computed_id'] for c in value['computed_facts']]}]}
            return httpx.Response(200, json={'id': f'response-{len(requests)}', 'object': 'chat.completion', 'created': 1,
                'model': 'test-deepseek', 'choices': [{'index': 0, 'finish_reason': 'stop',
                    'message': {'role': 'assistant', 'content': json.dumps(decision)}}],
                'usage': {'prompt_tokens': 100, 'completion_tokens': 50, 'total_tokens': 150}})

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            budget = RunBudget(root / 'budget.sqlite', '1')
            async def execute():
                async with AsyncOpenAI(api_key='test-key', base_url='https://api.deepseek.com', max_retries=0,
                    http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond))) as client:
                    model = DeepSeekChatCompletionsModel(model='deepseek-flash', openai_client=client)
                    metered = MeteredModel(model, root / 'calls', 'planner', 'deepseek', 'deepseek-flash',
                                          pricing_snapshot('deepseek', 'deepseek-flash'), budget)
                    return await DataQueryAgent(fixture.port, SdkQueryPlanner(metered)).run(request, output=root / 'session')
            result = asyncio.run(execute())
            self.assertEqual(result['status'], 'answered')
            self.assertEqual(result['computed_facts'][0]['display_decimal'], '15.00')
            self.assertEqual(len(requests), 2)
            self.assertEqual(summarize(root / 'calls')['unknown_cost_requests'], 0)
            self.assertEqual(budget.summary()['requests'], 2)
            for body in requests:
                self.assertEqual(body['response_format'], {'type': 'json_object'})
                self.assertEqual(body['thinking'], {'type': 'disabled'})
                self.assertIn('PlannerDecision', body['messages'][0]['content'])
            self.assertIn('computed_facts', requests[1]['messages'][-1]['content'])
