"""Offline wire-contract tests: real SDK/Runner, mocked HTTP only."""
import asyncio
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx2 as httpx
from openai import AsyncOpenAI

from uteki.agents.call_costs import estimate, pricing_snapshot
from uteki.agents.local_credentials import load_provider_key

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('consumer', ROOT/'scripts/run_research_data_consumer_comparison.py')
consumer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(consumer)


class DeepSeekConsumerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.prepared = self.root/'prepared'
        self.prepared.mkdir()
        block = dict(document_id='d', index_id='i', block_id='b', text='source quote')
        for case in ('A1', 'A2'):
            for arm in ('before', 'after'):
                packet = {'blocks': [block]}
                if arm == 'after':
                    packet['records'] = [{'evidence': block}]
                consumer.save(self.prepared/'step-05'/case/f'{arm}-input.json', packet)
            consumer.save(self.prepared/'step-05'/case/'comparison-design.json', {'question': case})
        consumer.save(self.prepared/'manifest.json', {'files': {
            str(p.relative_to(self.prepared)): consumer.digest(p.read_bytes())
            for p in self.prepared.rglob('*.json')}})
        self.answer = dict(status='answered', claims=[dict(text='claim', citations=[
            dict(document_id='d', index_id='i', block_id='b', quote='source quote')])],
            limitations=[], findings=[], stop_reason='done')
        self.requests = []

    def completion(self):
        return dict(id='response-test', object='chat.completion', created=1,
                    model='deepseek-v4.1-flash-test',
                    choices=[dict(index=0, finish_reason='stop',
                                  message=dict(role='assistant', content=json.dumps(self.answer)))],
                    usage=dict(prompt_tokens=100, completion_tokens=20, total_tokens=120,
                               prompt_cache_hit_tokens=40, prompt_cache_miss_tokens=60,
                               completion_tokens_details={'reasoning_tokens': 0}))

    def execute(self, payload=None, *, status=200, budget='1', provider='deepseek', model=None, max_output_tokens=2200):
        payload = self.completion() if payload is None else payload
        def respond(request):
            self.requests.append(request)
            return httpx.Response(status, json=payload, headers={'x-request-id': 'request-test'})

        async def invoke():
            async with AsyncOpenAI(api_key='test-key', base_url='https://api.deepseek.com',
                                   max_retries=0,
                                   http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond))) as client:
                with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'test-key', 'AIHUBMIX_API_KEY': 'test-key'}), \
                     patch('uteki.agents.analysis_comparison.AsyncOpenAI', return_value=client) as factory:
                    result = await consumer.run(self.prepared, self.root/'output', model, budget, provider, max_output_tokens)
                    self.factory_kwargs = factory.call_args.kwargs
                    return result
        with contextlib.redirect_stdout(io.StringIO()):
            return asyncio.run(invoke())

    def records(self):
        return [json.loads(p.read_text()) for p in (self.root/'output').rglob('*-end.json')]

    def test_real_sdk_sends_json_mode_and_independent_counterbalanced_pairs(self):
        result = self.execute()
        self.assertEqual(result['status'], 'completed_candidates_need_semantic_review')
        self.assertEqual(len(self.requests), 8)
        self.assertEqual(self.factory_kwargs['base_url'], 'https://api.deepseek.com')
        self.assertEqual(self.factory_kwargs['max_retries'], 0)
        self.assertEqual([(r['case'], r['arm'], r['repeat']) for r in result['runs']], [
            ('A1', 'before', 1), ('A1', 'after', 1), ('A2', 'before', 1), ('A2', 'after', 1),
            ('A1', 'after', 2), ('A1', 'before', 2), ('A2', 'after', 2), ('A2', 'before', 2)])
        manifest = json.loads((self.root/'output/manifest.json').read_text())
        self.assertTrue(manifest['implementation_sha256'])
        for request, row in zip(self.requests, result['runs']):
            body = json.loads(request.content)
            self.assertEqual(str(request.url), 'https://api.deepseek.com/chat/completions')
            self.assertEqual(body['model'], 'deepseek-flash')
            self.assertEqual(body['response_format'], {'type': 'json_object'})
            self.assertEqual(body['thinking'], {'type': 'disabled'})
            self.assertEqual(body['max_tokens'], 2200)
            for name in ('store', 'reasoning_effort', 'tools', 'parallel_tool_calls'):
                self.assertNotIn(name, body)
            self.assertEqual(len(body['messages']), 2)
            self.assertEqual(body['messages'][0]['content'], manifest['effective_instructions'])
            saved = json.loads((self.root/'output'/row['folder']/'request.json').read_text())
            self.assertEqual(saved['instructions'], body['messages'][0]['content'])
            self.assertEqual(saved['input'], body['messages'][1]['content'])
        for record in self.records():
            self.assertEqual(record['actual_upstream_model'], 'deepseek-v4.1-flash-test')
            self.assertEqual(record['request_id'], 'request-test')
            self.assertEqual(record['response_id'], 'response-test')
            self.assertEqual(record['finish_reason'], 'stop')
            self.assertEqual(record['usage']['input_tokens_details']['cached_tokens'], 40)
            self.assertEqual(record['estimated_usd'], '0.000054')

    def test_aihubmix_keeps_its_existing_wire_contract(self):
        result = self.execute(provider='aihubmix')
        self.assertEqual(result['status'], 'completed_candidates_need_semantic_review')
        self.assertEqual(self.factory_kwargs['base_url'], 'https://aihubmix.com/v1')
        for request in self.requests:
            body = json.loads(request.content)
            self.assertEqual(body['model'], 'gpt-5.4-mini')
            self.assertEqual(body['response_format']['type'], 'json_schema')
            self.assertNotIn('thinking', body)

    def test_expanded_limit_applies_to_every_arm_and_is_frozen(self):
        result = self.execute(max_output_tokens=3500)
        self.assertEqual(result['status'], 'completed_candidates_need_semantic_review')
        self.assertTrue(all(json.loads(request.content)['max_tokens'] == 3500 for request in self.requests))
        manifest = json.loads((self.root/'output/manifest.json').read_text())
        self.assertEqual(manifest['max_output_tokens'], 3500)
        self.assertEqual(len(list((self.root/'output').rglob('raw-output.txt'))), 8)

    def test_invalid_limit_rejected_without_creating_run(self):
        with self.assertRaises(ValueError):
            self.execute(max_output_tokens=0)
        self.assertEqual(self.requests, [])
        self.assertFalse((self.root/'output').exists())

    def test_invalid_json_or_schema_is_failed_with_cost_preserved(self):
        for content in ('{"status":', '{"status":"answered"}'):
            with self.subTest(content=content):
                payload = self.completion()
                payload['choices'][0]['message']['content'] = content
                # Each experiment is immutable, even inside this test.
                self.root = self.root/str(len(content))
                self.root.mkdir()
                self.requests = []
                result = self.execute(payload)
                self.assertEqual(result['status'], 'completed_with_failures')
                self.assertTrue(all(r['status'] == 'failed' for r in result['runs']))
                self.assertEqual(result['budget']['unknown_requests'], 0)
                self.assertEqual(len(self.records()), 8)
                self.assertTrue(all(r['estimated_usd'] == '0.000054' for r in self.records()))
                self.assertFalse(list((self.root/'output').rglob('answer.json')))

    def test_truncated_valid_json_is_rejected_and_charged(self):
        payload = self.completion()
        payload['choices'][0]['finish_reason'] = 'length'
        result = self.execute(payload)
        self.assertEqual(result['status'], 'completed_with_failures')
        self.assertEqual(result['budget']['unknown_requests'], 0)
        self.assertTrue(all(r['finish_reason'] == 'length' for r in self.records()))
        self.assertTrue(all(r['estimated_usd'] == '0.000054' for r in self.records()))
        self.assertFalse(list((self.root/'output').rglob('answer.json')))

    def test_empty_response_is_rejected(self):
        payload = self.completion()
        payload['choices'][0]['message']['content'] = ''
        result = self.execute(payload)
        self.assertEqual(result['status'], 'completed_with_failures')
        self.assertEqual(result['budget']['unknown_requests'], 0)
        self.assertFalse(list((self.root/'output').rglob('answer.json')))

    def test_missing_usage_stops_instead_of_recording_zero_cost(self):
        payload = self.completion()
        del payload['usage']
        result = self.execute(payload)
        self.assertEqual(result['status'], 'stopped_unknown_cost')
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(result['budget']['unknown_requests'], 1)
        self.assertIsNone(self.records()[0]['estimated_usd'])

    def test_http_failure_stops_without_retry_or_logging_secret(self):
        result = self.execute({'error': {'message': 'private-key-do-not-log', 'type': 'auth_error'}}, status=401)
        self.assertEqual(result['status'], 'stopped_unknown_cost')
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.records()[0]['http_status'], 401)
        self.assertNotIn('private-key-do-not-log', json.dumps(self.records()))

    def test_budget_exhaustion_makes_no_http_request(self):
        result = self.execute(budget='0.000001')
        self.assertEqual(result['status'], 'stopped_budget')
        self.assertEqual(len(self.requests), 0)
        self.assertEqual(result['budget']['requests'], 0)

    def test_wrong_quote_is_not_a_valid_candidate(self):
        self.answer['claims'][0]['citations'][0]['quote'] = 'fabricated'
        result = self.execute()
        self.assertEqual(result['status'], 'completed_with_failures')
        self.assertTrue(all(r['status'] == 'invalid_citations' for r in result['runs']))

    def test_unknown_models_rejected_before_output_creation(self):
        with self.assertRaises(ValueError):
            self.execute(model='deepseek-chat')
        self.assertFalse((self.root/'output').exists())
        self.assertEqual(consumer.resolve_model('aihubmix'), 'gpt-5.4-mini')
        self.assertEqual(consumer.resolve_model('deepseek', 'deepseek-v4-pro'), 'deepseek-v4-pro')

    def test_current_usd_peak_prices_do_not_double_count_cache_or_reasoning(self):
        usage = dict(input_tokens=1000000, output_tokens=1000000,
                     input_tokens_details={'cached_tokens': 100},
                     output_tokens_details={'reasoning_tokens': 500})
        self.assertEqual(estimate(usage, pricing_snapshot('deepseek', 'deepseek-flash')), '1.50')
        self.assertEqual(estimate(usage, pricing_snapshot('deepseek', 'deepseek-v4-pro')), '5.28')
        self.assertIsNone(pricing_snapshot('deepseek', 'gpt-5.4-mini'))

    def test_credentials_load_only_selected_provider(self):
        path = self.root/'.env'
        path.write_text('AIHUBMIX_API_KEY=not-selected\nexport DEEPSEEK_API_KEY="test-key"\n')
        path.chmod(0o600)
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(load_provider_key(self.root, 'deepseek'), 'local_env_file')
            self.assertEqual(os.environ['DEEPSEEK_API_KEY'], 'test-key')
            self.assertNotIn('AIHUBMIX_API_KEY', os.environ)
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'environment-key'}, clear=True):
            self.assertEqual(load_provider_key(self.root, 'deepseek'), 'environment')
            self.assertEqual(os.environ['DEEPSEEK_API_KEY'], 'environment-key')

    def test_invalid_credentials_rejected_without_execution(self):
        path = self.root/'.env'
        for value in ('DEEPSEEK_API_KEY=$(touch should-not-exist)',
                      'DEEPSEEK_API_KEY=a\nDEEPSEEK_API_KEY=b', 'DEEPSEEK_API_KEY='):
            path.write_text(value)
            path.chmod(0o600)
            with patch.dict(os.environ, {}, clear=True), self.assertRaises(ValueError):
                load_provider_key(self.root, 'deepseek')
        path.write_text('DEEPSEEK_API_KEY=test-key')
        path.chmod(0o644)
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(ValueError):
            load_provider_key(self.root, 'deepseek')


if __name__ == '__main__':
    unittest.main()
