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
    def test_question_proposal_execution_and_finish_share_metered_model(self):
        from tests.unit.test_scoped_query_service import make_scoped_dataset
        from tests.unit.test_task_completion import attach_synthetic_quotes
        from tests.unit.test_task_progress import plan
        from uteki.infrastructure.research_data.query_service import QueryDataPort
        requests = []
        def respond(http_request):
            body = json.loads(http_request.content); requests.append(body)
            packet = json.loads(body['messages'][-1]['content'])
            if 'catalog' in packet:
                self.assertNotIn('tasks', packet['request'])
                decision = {'action': 'plan', 'tasks': plan()['tasks'][1:]}
            elif packet['completion']['finish_allowed']:
                decision = {'action': 'finish'}
            else:
                task = packet['plan']['tasks'][0]; req = task['requirements'][0]
                decision = {'action': 'execute', 'step': {'task_id': task['task_id'], 'requirement_id': req['requirement_id'],
                            'action': 'query', 'query': req['query']}}
            return httpx.Response(200, json={'id': f'test-{len(requests)}', 'object': 'chat.completion', 'created': 1,
                'model': 'test-deepseek', 'choices': [{'index': 0, 'finish_reason': 'stop',
                    'message': {'role': 'assistant', 'content': json.dumps(decision)}}],
                'usage': {'prompt_tokens': 100, 'completion_tokens': 50, 'total_tokens': 150}})
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); dataset = root / 'dataset'; dataset.mkdir()
            make_scoped_dataset(dataset); attach_synthetic_quotes(dataset)
            budget = RunBudget(root / 'budget.sqlite', '1')
            async def execute():
                with QueryDataPort(dataset) as port:
                    async with AsyncOpenAI(api_key='test-key', base_url='https://api.deepseek.com', max_retries=0,
                        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond))) as client:
                        inner = DeepSeekChatCompletionsModel(model='deepseek-flash', openai_client=client)
                        metered = MeteredModel(inner, root / 'calls', 'planner', 'deepseek', 'deepseek-flash',
                                              pricing_snapshot('deepseek', 'deepseek-flash'), budget)
                        return await DataQueryAgent(port, SdkQueryPlanner(metered, task_mode=True), max_steps=3).run_question(
                            {'question': 'Get operating margin for FY2031.', 'scope': plan()['scope']}, output=root / 'run')
            result = asyncio.run(execute())
            self.assertEqual(result['status'], 'retrieval_satisfied')
            self.assertEqual(result['execution']['plan_origin'], 'model')
            self.assertEqual(len(requests), 3)
            self.assertEqual(budget.summary()['requests'], 3)
            self.assertEqual(summarize(root / 'calls')['unknown_cost_requests'], 0)

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
