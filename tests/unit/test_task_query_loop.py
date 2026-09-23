"""Targeted checks for the task-driven loop; no providers or browser review."""
import asyncio
import json
from pathlib import Path
import tempfile
import unittest

from scripts.run_task_query_loop import FeedbackFixturePlanner, run_fixture, ROOT
from uteki.agents.data_query_agent import DataQueryAgent
from uteki.infrastructure.research_data.query_service import QueryDataPort
from tests.unit.test_scoped_query_service import make_scoped_dataset
from tests.unit.test_task_progress import plan, read_step
from tests.unit.test_task_completion import attach_synthetic_quotes


class TaskQueryLoopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.dataset = self.root / 'dataset'; self.dataset.mkdir()
        make_scoped_dataset(self.dataset); attach_synthetic_quotes(self.dataset)
        self.port = QueryDataPort(self.dataset); self.addCleanup(self.port.close)

    def run_loop(self, planner, configured=None, **limits):
        return asyncio.run(DataQueryAgent(self.port, planner, **limits).run_tasks(
            configured or plan(), output=self.root / 'run'))

    def test_rejected_finish_followed_by_feedback_driven_reads_and_query_succeeds(self):
        configured = plan(); configured['tasks'][1]['depends_on'] = ['business']
        result = self.run_loop(FeedbackFixturePlanner(read_count=2), configured, max_steps=6)
        self.assertEqual(result['status'], 'retrieval_satisfied')
        self.assertEqual(result['turns'][0]['feedback'], 'finish_rejected')
        self.assertEqual(result['turns'][-1]['feedback'], 'finish_accepted')
        self.assertEqual(result['tool_steps'], 3)
        self.assertTrue(result['completion']['finish_allowed'])
        self.assertEqual(result['semantic_completeness'], 'not_evaluated')
        self.assertEqual(self.port.scoped(configured['scope']).scope.source_snapshot_ids, ('acme-annual',))

    def test_wrong_source_is_rejected_and_planner_can_correct_from_feedback(self):
        class CorrectingPlanner(FeedbackFixturePlanner):
            def __init__(self): super().__init__(probe_early_finish=False); self.first = True
            async def decide(self, packet):
                if self.first:
                    self.first = False
                    wrong = read_step(); wrong['read']['source_snapshot_id'] = 'other-annual'
                    return {'action': 'execute', 'step': wrong}
                return await super().decide(packet)
        result = self.run_loop(CorrectingPlanner(), max_steps=5)
        self.assertEqual(result['turns'][0]['feedback'], 'error')
        self.assertEqual(result['turns'][0]['progress'][0]['requirements'][0]['returned_count'], 0)
        self.assertEqual(result['status'], 'retrieval_satisfied')

    def test_repeated_no_progress_stops_with_unread_range(self):
        class Repeater:
            async def decide(self, packet): return {'action': 'execute', 'step': read_step()}
        result = self.run_loop(Repeater(), max_steps=6)
        self.assertEqual(result['status'], 'limited')
        self.assertEqual(result['stop_reason'], 'no_progress_limit')
        self.assertEqual(result['planner_attempts'], 4)
        self.assertEqual(result['progress'][0]['requirements'][0]['unread_count'], 2)

    def test_decision_limit_includes_rejected_finish_and_preserves_remaining_work(self):
        result = self.run_loop(FeedbackFixturePlanner(read_count=1), max_steps=2)
        self.assertEqual(result['status'], 'limited')
        self.assertEqual(result['stop_reason'], 'decision_limit')
        self.assertEqual(result['planner_attempts'], 2)
        self.assertEqual(result['tool_steps'], 1)
        self.assertEqual(result['decisions_remaining'], 0)
        self.assertFalse(result['completion']['finish_allowed'])

    def test_context_limit_prevents_planner_call(self):
        class NeverCalled:
            async def decide(self, packet): raise AssertionError('must not call planner')
        result = self.run_loop(NeverCalled(), max_packet_bytes=1000)
        self.assertEqual(result['status'], 'limited')
        self.assertEqual(result['stop_reason'], 'context_budget_exceeded')
        self.assertEqual(result['planner_attempts'], 0)

    def test_malformed_decision_does_not_create_a_tool_event_and_can_be_corrected(self):
        class CorrectingPlanner(FeedbackFixturePlanner):
            def __init__(self): super().__init__(probe_early_finish=False); self.first = True
            async def decide(self, packet):
                if self.first:
                    self.first = False
                    return {'action': 'finish', 'completed': True}
                return await super().decide(packet)
        result = self.run_loop(CorrectingPlanner(), max_steps=5)
        self.assertEqual(result['turns'][0]['feedback'], 'invalid_decision')
        self.assertIsNone(result['turns'][0]['event_sequence'])
        self.assertEqual(result['status'], 'retrieval_satisfied')

    def test_real_fixture_returns_all_selected_body_and_numeric_evidence(self):
        result = asyncio.run(run_fixture(ROOT / 'experiments/data_agent_query/task-react-v1/spec.json', self.root / 'real'))
        self.assertEqual(result['status'], 'retrieval_satisfied')
        body = result['progress'][0]['requirements'][0]
        self.assertEqual((body['returned_count'], body['required_count'], body['unread_count']), (79, 79, 0))
        self.assertEqual(result['tool_steps'], 8)
        self.assertEqual(result['planner_attempts'], 10)
        verification = json.loads((self.root / 'real/verification.json').read_text())
        self.assertEqual(verification['model_calls'], 0)
        self.assertTrue(verification['dataset_unchanged'])

    def test_question_creates_plan_without_caller_tasks_and_counts_proposal_in_limit(self):
        class Proposer(FeedbackFixturePlanner):
            plan_origin = "scripted_fixture"
            async def draft_plan(self, packet):
                self.packet = packet
                return {'action': 'plan', 'tasks': plan()['tasks'][1:]}
        planner = Proposer(probe_early_finish=False)
        request = {'question': 'Get operating margin for FY2031.', 'scope': plan()['scope']}
        result = asyncio.run(DataQueryAgent(self.port, planner, max_steps=3).run_question(request, output=self.root / 'question'))
        self.assertEqual(result['status'], 'retrieval_satisfied')
        self.assertEqual(result['planning_calls'], 1)
        self.assertEqual(result['execution']['planner_attempts'], 2)
        self.assertNotIn('tasks', planner.packet['request'])
        self.assertEqual(planner.packet['request']['question'], request['question'])
        saved = json.loads((self.root / 'question/plan.json').read_text())
        self.assertEqual(saved['origin'], 'scripted_fixture')
        self.assertEqual(saved['scope'], planner.packet['request']['scope'])
        report = (self.root / 'question/report.md').read_text()
        self.assertIn('实际 SQL', report)
        self.assertIn('retrieval\\_satisfied', report)
        self.assertIn('acme-services', report)
        self.assertTrue((self.root / 'question/report-source-text.md').exists())

    def test_ungrounded_model_period_cannot_become_a_task(self):
        class Proposer:
            plan_origin = "scripted_fixture"
            async def draft_plan(self, packet): return {'action': 'plan', 'tasks': plan()['tasks'][1:]}
            async def decide(self, packet): raise AssertionError('must not execute ungrounded plan')
        result = asyncio.run(DataQueryAgent(self.port, Proposer()).run_question(
            {'question': 'Get operating margin.', 'scope': plan()['scope']}, output=self.root / 'ungrounded'))
        self.assertEqual(result['status'], 'invalid_plan')
        self.assertNotIn('execution', result)

    def test_proposal_can_clarify_and_one_remaining_request_cannot_start_execution(self):
        class Clarifier:
            plan_origin = "scripted_fixture"
            async def draft_plan(self, packet): return {'action': 'clarify', 'clarification': 'Which year?'}
        request = {'question': 'Get operating margin.', 'scope': plan()['scope']}
        result = asyncio.run(DataQueryAgent(self.port, Clarifier(), max_steps=1).run_question(request, output=self.root / 'clarify'))
        self.assertEqual(result['status'], 'needs_clarification')
        self.assertEqual(result['planning_calls'], 1)
        self.assertIn('Which year?', (self.root / 'clarify/report.md').read_text())
        self.assertIn('未生成有效任务计划', (self.root / 'clarify/report.md').read_text())
        class Proposer:
            plan_origin = "scripted_fixture"
            async def draft_plan(self, packet): return {'action': 'plan', 'tasks': plan()['tasks'][1:]}
            async def decide(self, packet): raise AssertionError('proposal used the last request')
        request['question'] = 'Get operating margin for FY2031.'
        result = asyncio.run(DataQueryAgent(self.port, Proposer(), max_steps=1).run_question(request, output=self.root / 'limit'))
        self.assertEqual(result['status'], 'limited')
        self.assertEqual(result['stop_reason'], 'decision_limit')
        self.assertNotIn('execution', result)

    def test_question_rejects_unknown_planner_origin_before_call_or_output(self):
        class UnknownPlanner:
            async def draft_plan(self, packet):
                raise AssertionError("unknown provenance must be rejected before calling")
        request = {'question': 'Get operating margin for FY2031.', 'scope': plan()['scope']}
        for origin in (None, '', 'caller', 'unrecognized'):
            with self.subTest(origin=origin):
                planner = UnknownPlanner()
                if origin is not None:
                    planner.plan_origin = origin
                output = self.root / 'unknown-origin'
                with self.assertRaisesRegex(ValueError, 'plan_origin'):
                    asyncio.run(DataQueryAgent(self.port, planner).run_question(request, output=output))
                self.assertFalse(output.exists())
