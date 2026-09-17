import asyncio
from dataclasses import dataclass
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from uteki.agents.call_costs import MeteredModel, estimate, pricing_snapshot, summarize


class CostTests(unittest.TestCase):
    def test_estimate_does_not_double_count_cache_or_reasoning(self):
        price = pricing_snapshot('aihubmix', 'gpt-5.4-mini')
        usage = {'input_tokens': 1000000, 'output_tokens': 1000000,
                 'input_tokens_details': {'cached_tokens': 100},
                 'output_tokens_details': {'reasoning_tokens': 500}}
        self.assertEqual(estimate(usage, price), '5.25')
        self.assertIsNone(estimate(None, price))
        self.assertIsNone(estimate(usage, None))

    def test_success_and_failure_persist_independently(self):
        @dataclass
        class Usage:
            input_tokens: int = 100
            output_tokens: int = 20
        class Fake:
            async def get_response(self):
                return SimpleNamespace(usage=Usage(), response_id='response-test', request_id='request-test')
        class Fail:
            async def get_response(self):
                raise TimeoutError('secret must not be logged')
        with tempfile.TemporaryDirectory() as tmp:
            p = pricing_snapshot('aihubmix', 'gpt-5.4-mini')
            asyncio.run(MeteredModel(Fake(), tmp, 'analyst', 'aihubmix', 'gpt-5.4-mini', p).get_response())
            with self.assertRaises(TimeoutError):
                asyncio.run(MeteredModel(Fail(), tmp, 'reviewer', 'aihubmix', 'gpt-5.4-mini', p).get_response())
            report = summarize(tmp)
            self.assertEqual(report['requests'], 2)
            self.assertEqual(report['unknown_cost_requests'], 1)
            self.assertNotIn('secret', json.dumps(report))
            self.assertEqual(len(list(Path(tmp).glob('*-start.json'))), 2)

    def test_cancelled_request_is_recorded(self):
        class Cancel:
            async def get_response(self):
                raise asyncio.CancelledError()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(asyncio.CancelledError):
                asyncio.run(MeteredModel(Cancel(), tmp, 'a', 'unknown', 'm', None).get_response())
            self.assertEqual(summarize(tmp)['unknown_cost_requests'], 1)
