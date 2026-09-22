"""Host-loop tests. Scripted planners verify mechanics, not language understanding."""
import asyncio
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from uteki.agents.data_query_agent import DataQueryAgent
from uteki.agents.data_query_model import check_prior_budgets
from uteki.agents.run_budget import RunBudget
from uteki.domain.research_data.agent_query import AgentQuery
from uteki.domain.research_data.period_scope import explicit_periods, validate_plan_periods
from uteki.domain.research_data.agent_query import QueryPlan
from uteki.infrastructure.research_data.query_service import QueryDataPort
from tests.unit import test_query_scope

ROOT = Path(__file__).resolve().parents[2]


class ScriptedPlanner:
    def __init__(self, actions):
        self.actions, self.packets = iter(actions), []

    async def decide(self, packet):
        self.packets.append(copy.deepcopy(packet))
        action = next(self.actions)
        return action(packet) if callable(action) else action


def reference_finish(packet):
    value = packet['history'][-1]['result']
    return {'action': 'finish', 'answer_parts': [{'requested_information': 'Requested source-backed data',
        'record_ids': [r['record_id'] for r in value.get('records', [])],
        'computed_ids': [r['computed_id'] for r in value.get('computed_facts', [])],
        'context_ids': [r['context_id'] for r in value.get('contexts', [])],
        'gap_ids': [r['gap_id'] for r in value.get('gaps', [])]}]}


class DataQueryAgentTests(unittest.TestCase):
    def setUp(self):
        fixture = test_query_scope.QueryScopeTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.port = fixture.port
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / 'session'
        self.request = {'question': 'What is the operating margin of Acme Services in 2031 Q2?',
            'company_ids': ['acme'], 'snapshot_id': self.port.snapshot_id, 'source_policy_id': 'local-frozen-v1',
            'knowledge_cutoff': '2031-07-21', 'include_candidates': True}
        self.plan = {'action': 'query', 'plan': {'calculations': [{'formula_id': 'operating_margin',
            'entity_id': 'acme-services', 'periods': [{'kind': 'quarter', 'start': '2031-04-01', 'end': '2031-06-30'}]}]}}

    def run_agent(self, actions, request=None, **limits):
        self.planner = ScriptedPlanner(actions)
        return asyncio.run(DataQueryAgent(self.port, self.planner, **limits).run(request or self.request, output=self.output))

    def test_two_round_query_returns_host_calculation_and_complete_audit(self):
        result = self.run_agent([self.plan, reference_finish])
        self.assertEqual(result['status'], 'answered')
        self.assertEqual(result['computed_facts'][0]['display_decimal'], '15.00')
        self.assertEqual(len(self.planner.packets), 2)
        self.assertEqual(self.planner.packets[0]['history'], [])
        self.assertNotIn('plan', self.planner.packets[0]['request'])
        self.assertEqual({e['entity_id'] for e in self.planner.packets[0]['catalog']['entities']}, {'acme', 'acme-services'})
        self.assertEqual({s['company_id'] for s in self.planner.packets[0]['catalog']['sources']}, {'acme'})
        self.assertTrue(any(t['tool'] == 'sql' for t in self.planner.packets[1]['history'][0]['result']['trace']))
        self.assertTrue((self.output / 'turn-02/decision.json').exists())

    def test_no_company_default_and_no_question_only_guess(self):
        for scope in ([], [' ']):
            with self.subTest(scope=scope), self.assertRaises(ValidationError):
                AgentQuery.model_validate({**self.request, 'company_ids': scope})
        request = {**self.request, 'question': 'How is the margin?'}
        result = self.run_agent([{'action': 'clarify', 'clarification': 'Which reporting period do you mean?'}], request)
        self.assertEqual(result['status'], 'needs_clarification')
        self.assertEqual(result['records'], [])

    def test_model_invented_period_is_blocked_before_query(self):
        with patch.object(self.port, 'query_data') as query:
            result = self.run_agent([self.plan], {**self.request, 'question': 'What is Acme Services operating margin?'})
        query.assert_not_called()
        self.assertEqual(result['status'], 'needs_clarification')
        self.assertFalse(result['records'] or result['computed_facts'])

    def test_wrong_quarter_cannot_replace_explicit_quarter(self):
        request = {**self.request, 'question': 'What is Acme Services operating margin in 2031 Q1?'}
        with patch.object(self.port, 'query_data') as query:
            result = self.run_agent([self.plan], request, max_steps=1)
        query.assert_not_called()
        self.assertEqual(result['status'], 'limited')
        self.assertIn('not explicitly grounded', result['trace'][0]['message'])

    def test_unexpected_tool_failure_is_recorded_without_sensitive_message(self):
        with patch.object(self.port, 'query_data', side_effect=RuntimeError('sensitive execution detail')):
            result = self.run_agent([self.plan])
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['error'], 'RuntimeError')
        self.assertNotIn('sensitive execution detail', json.dumps(result))

    def test_cross_company_plan_rejected_then_model_can_correct(self):
        wrong = copy.deepcopy(self.plan)
        wrong['plan']['calculations'][0]['entity_id'] = 'other'
        result = self.run_agent([wrong, self.plan, reference_finish])
        self.assertEqual(result['status'], 'answered')
        self.assertIn('outside', self.planner.packets[1]['history'][0]['result']['message'])
        self.assertEqual({r['entity_id'] for r in result['records']}, {'acme-services'})

    def test_model_cannot_override_candidate_access_or_snapshot(self):
        wrong = copy.deepcopy(self.plan)
        wrong['plan']['include_candidates'] = True
        result = self.run_agent([wrong, self.plan, reference_finish], {**self.request, 'include_candidates': False})
        self.assertEqual(result['status'], 'unanswerable')
        self.assertEqual(result['records'], [])
        self.assertEqual(result['gaps'][0]['reason'], 'quality_filtered')

    def test_cutoff_not_relaxed_by_planner(self):
        result = self.run_agent([self.plan, reference_finish], {**self.request, 'knowledge_cutoff': '2031-07-19'})
        self.assertEqual(result['status'], 'unanswerable')
        self.assertFalse(result['records'] or result['evidence'])
        self.assertIn('not_available_at_cutoff', {g['reason'] for g in result['gaps']})

    def test_fabricated_reference_is_rejected_before_returning_answer(self):
        wrong = {'action': 'finish', 'answer_parts': [{'requested_information': 'Revenue', 'record_ids': ['invented']}]}
        result = self.run_agent([wrong, wrong], max_steps=2)
        self.assertEqual(result['status'], 'limited')
        self.assertEqual(result['records'], [])
        self.assertEqual(result['answer_parts'], [])

    def test_unknown_company_never_calls_model(self):
        result = self.run_agent([], {**self.request, 'company_ids': ['unknown-company']})
        self.assertEqual(result['status'], 'unanswerable')
        self.assertEqual(self.planner.packets, [])

    def test_cross_company_context_read_never_reaches_reader(self):
        with patch.object(self.port, 'read_context') as reader:
            result = self.run_agent([{'action': 'read_context', 'context': {'source_snapshot_id': 'other-call', 'block_id': 'b'}}], max_steps=1)
            reader.assert_not_called()
        self.assertEqual(result['status'], 'limited')

    def test_invalid_decision_has_bounded_retries(self):
        result = self.run_agent([{'action': 'query', 'plan': {}}] * 2, max_steps=2)
        self.assertEqual(result['status'], 'limited')
        self.assertEqual(len(self.planner.packets), 2)

    def test_output_is_immutable_and_context_limit_is_explicit(self):
        result = self.run_agent([], max_packet_bytes=1000)
        self.assertEqual(result['status'], 'limited')
        self.assertIn('context_budget_exceeded', result['error'])
        with self.assertRaises(FileExistsError):
            self.run_agent([])

    def test_model_failure_does_not_expose_exception_message(self):
        def fail(packet):
            raise RuntimeError('sensitive-provider-response')
        result = self.run_agent([fail])
        self.assertEqual(result['error'], 'RuntimeError')
        self.assertNotIn('sensitive-provider-response', json.dumps(result))

    def test_prior_unknown_cost_guard_is_read_only_and_not_folder_scoped(self):
        path = Path(self.temp.name) / 'prior.sqlite'
        budget = RunBudget(path, '1')
        token = budget.reserve('0.01')
        budget.settle(token, None)
        before = path.read_bytes()
        status = check_prior_budgets([path])
        self.assertEqual(status['status'], 'blocked')
        self.assertEqual(status['prior_budgets'][0]['unresolved'][0]['state'], 'unknown')
        self.assertEqual(path.read_bytes(), before)
        approved = [{'path': path, 'reservation_id': token, 'reserved_usd': '0.01'}]
        self.assertEqual(check_prior_budgets([path], acknowledged_unknowns=approved)['status'], 'ready_with_acknowledged_unknown_cost')
        self.assertEqual(path.read_bytes(), before)
        approved[0]['reservation_id'] = 'different-request'
        self.assertEqual(check_prior_budgets([path], acknowledged_unknowns=approved)['status'], 'blocked')


class RealSourceLoopTests(unittest.TestCase):
    def test_filing_search_uses_declared_document_node_and_preserves_source(self):
        with QueryDataPort(ROOT / 'experiments/data_agent_query/2026-09-22-pilot-04/dataset') as port:
            for form, end in [('10-K', '2025-12-31'), ('10-Q', '2026-03-31')]:
                with self.subTest(form=form):
                    result = port.query_data({'query_id': 'root-node-regression', 'snapshot_id': port.snapshot_id,
                        'knowledge_cutoff': '2026-09-22', 'include_candidates': True,
                        'documents': [{'company_id': 'alphabet', 'form': form, 'period_end': end, 'phrase': 'Google Cloud'}]})
                    contexts = result['documents'][0]['contexts']
                    self.assertTrue(contexts)
                    ctx = contexts[0]
                    reread = port.read_context(source_snapshot_id=ctx['source_snapshot_id'],
                        block_id=ctx['anchor_block_id'], snapshot_id=port.snapshot_id,
                        knowledge_cutoff='2026-09-22', include_candidates=True)
                    self.assertIn('Google Cloud', json.dumps(reread['blocks']))
                    self.assertNotEqual(reread['node_id'], 'document')

    def test_document_node_must_be_unambiguous_and_is_not_a_fixed_name(self):
        from types import SimpleNamespace
        reader = SimpleNamespace(index={'nodes': [{'kind': 'document', 'node_id': 'independent-root'}]})
        self.assertEqual(QueryDataPort._document_node(reader), 'independent-root')
        for nodes in ([], [{'kind': 'document', 'node_id': 'one'}, {'kind': 'document', 'node_id': 'two'}]):
            with self.assertRaises(ValueError):
                QueryDataPort._document_node(SimpleNamespace(index={'nodes': nodes}))

    def test_literal_search_then_context_read_returns_original_qualifications(self):
        with tempfile.TemporaryDirectory() as tmp, QueryDataPort(ROOT / 'experiments/data_agent_query/2026-09-22-pilot-04/dataset') as port:
            request = {'question': '列出 2025 Q4 电话会的 CapEx 约束条件并回读原文。', 'company_ids': ['alphabet'],
                       'snapshot_id': port.snapshot_id, 'source_policy_id': 'local-frozen-v1',
                       'knowledge_cutoff': '2026-09-22', 'include_candidates': True}
            def followup(packet):
                ctx = packet['history'][-1]['result']['contexts'][0]
                return {'action': 'read_context', 'context': {'source_snapshot_id': ctx['source_snapshot_id'], 'block_id': ctx['anchor_block_id']}}
            def finish(packet):
                ctx = packet['history'][-1]['result']
                return {'action': 'finish', 'answer_parts': [{'requested_information': '付款时点限定', 'context_ids': [ctx['context_id']]}]}
            planner = ScriptedPlanner([{'action': 'query', 'plan': {'documents': [{'company_id': 'alphabet',
                'form': 'EARNINGS_CALL', 'period_end': '2025-12-31', 'phrase': 'timing of cash payments'}]}}, followup, finish])
            result = asyncio.run(DataQueryAgent(port, planner).run(request, output=Path(tmp) / 'session'))
            self.assertEqual(result['status'], 'answered')
            self.assertIn('timing of cash payments', json.dumps(result['contexts']))
            self.assertEqual([t['tool'] for t in result['trace']], ['query', 'read_context', 'finish'])


class PeriodScopeTests(unittest.TestCase):
    def test_literal_calendar_periods_in_both_languages(self):
        for text in ('Acme 2031 Q2 margin', 'Acme Q2 2031 margin', 'Acme 2031 年第二季度利润率'):
            with self.subTest(text=text):
                self.assertEqual([p.model_dump(mode='json') for p in explicit_periods(text)],
                                 [{'kind': 'quarter', 'start': '2031-04-01', 'end': '2031-06-30'}])
        self.assertEqual([p.kind for p in explicit_periods('2030 Q4 call guidance for FY2031')], ['quarter', 'year'])

    def test_missing_relative_ytd_and_unimplemented_range_never_become_full_year(self):
        for text in ('Operating margin?', 'latest margin', '2031 YTD revenue', '2031 上半年收入',
                     '2030-2031 revenue', '2031 年前三季度收入', '2031 年 6 月收入', 'Revenue of 2031 USD'):
            with self.subTest(text=text):
                self.assertEqual(explicit_periods(text), ())

    def test_source_period_cannot_be_inferred_from_target_year(self):
        plan = QueryPlan(documents=[{'company_id': 'acme', 'form': 'EARNINGS_CALL',
                                     'period_end': '2030-12-31', 'phrase': 'guidance'}])
        with self.assertRaises(ValueError):
            validate_plan_periods(plan, explicit_periods('FY2031 guidance'))
