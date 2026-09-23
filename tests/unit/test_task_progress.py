"""Independent company tests for task attribution and actual retrieval progress."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from uteki.domain.research_data.task_plan import TaskPlan, TaskStep
from uteki.infrastructure.research_data.financial_records import digest
from uteki.infrastructure.research_data.query_service import QueryDataPort
from uteki.infrastructure.research_data.task_progress import TaskProgressSession, replay_task_session
from tests.unit.test_scoped_query_service import make_scoped_dataset, year


def plan():
    return {'plan_id': 'independent-plan', 'origin': 'scripted_fixture', 'question': 'Read Business and calculate margin for FY2031.',
            'scope': {'snapshot_id': 'synthetic-scoped-v1', 'company_ids': ['acme'], 'source_snapshot_ids': ['acme-annual'],
                      'source_policy_id': 'local-frozen-v1', 'knowledge_cutoff': '2032-06-01', 'include_candidates': True},
            'tasks': [
                {'task_id': 'business', 'requested_information': 'Read the selected Business section.',
                 'source_snapshot_ids': ['acme-annual'], 'requirements': [{'kind': 'read_node', 'requirement_id': 'body',
                 'source_snapshot_id': 'acme-annual', 'node_id': 'business'}]},
                {'task_id': 'margin', 'requested_information': 'Retrieve inputs and compute margin for FY2031.',
                 'source_snapshot_ids': ['acme-annual'], 'requirements': [{'kind': 'query', 'requirement_id': 'margin',
                 'query': {'calculations': [{'formula_id': 'operating_margin', 'entity_id': 'acme-services', 'periods': [year(2031)]}]}}]}]}


def read_step(**changes):
    return {'task_id': 'business', 'requirement_id': 'body', 'action': 'read_source',
            'read': {'source_snapshot_id': 'acme-annual', 'node_id': 'business', 'count': 1, **changes}}


def query_step():
    return {'task_id': 'margin', 'requirement_id': 'margin', 'action': 'query',
            'query': plan()['tasks'][1]['requirements'][0]['query']}


def requirement(state, task_id='business', requirement_id='body'):
    return next(r for t in state['tasks'] if t['task_id'] == task_id
                for r in t['requirements'] if r['requirement_id'] == requirement_id)


class TaskPlanTests(unittest.TestCase):
    def test_missing_duplicate_or_outside_scope_and_bad_dependencies_are_rejected(self):
        variants = []
        for field in ('question', 'scope', 'origin', 'tasks'):
            candidate = plan(); del candidate[field]; variants.append(candidate)
        candidate = plan(); candidate['tasks'].append(copy.deepcopy(candidate['tasks'][0])); variants.append(candidate)
        candidate = plan(); candidate['tasks'][0]['source_snapshot_ids'] = ['other-annual']; variants.append(candidate)
        candidate = plan(); candidate['tasks'][0]['requirements'][0]['source_snapshot_id'] = 'other-annual'; variants.append(candidate)
        candidate = plan(); candidate['tasks'][0]['depends_on'] = ['missing']; variants.append(candidate)
        candidate = plan(); candidate['tasks'][0]['depends_on'] = ['margin']; candidate['tasks'][1]['depends_on'] = ['business']; variants.append(candidate)
        for candidate in variants:
            with self.subTest(candidate=candidate), self.assertRaises(ValidationError):
                TaskPlan.model_validate(candidate)

    def test_query_periods_cannot_be_inferred_from_source_coverage(self):
        for question in ('Read Business and calculate margin.', 'Calculate the latest margin.'):
            candidate = plan(); candidate['question'] = question
            with self.assertRaises(ValidationError):
                TaskPlan.model_validate(candidate)
        candidate = plan(); candidate['tasks'][1]['requirements'][0]['query']['calculations'][0]['periods'] = [year(2030)]
        with self.assertRaises(ValidationError):
            TaskPlan.model_validate(candidate)

    def test_sentence_punctuation_is_allowed_but_decimal_years_are_not(self):
        TaskPlan.model_validate(plan())  # FY2031 at the end of a sentence.
        candidate = plan(); candidate['question'] = 'Compute margin for FY2031.5'
        with self.assertRaises(ValidationError):
            TaskPlan.model_validate(candidate)

    def test_step_cannot_supply_progress_results_or_finish(self):
        for extra in ({'completed': True}, {'returned_body': ['b0']}, {'result': {'records': []}}, {'action': 'finish'}):
            with self.subTest(extra=extra), self.assertRaises(ValidationError):
                TaskStep.model_validate({**read_step(), **extra})

    def test_explicit_clarification_and_acyclic_dependency_are_representable(self):
        candidate = plan(); candidate['tasks'][1]['depends_on'] = ['business']
        candidate['tasks'][1]['requirements'] = [{'kind': 'clarification', 'requirement_id': 'period', 'question': 'Which period?'}]
        parsed = TaskPlan.model_validate(candidate)
        self.assertEqual(parsed.tasks[1].requirements[0].kind, 'clarification')
        self.assertEqual(parsed.tasks[1].depends_on, ('business',))


class TaskProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.dataset = self.root / 'dataset'; self.dataset.mkdir()
        make_scoped_dataset(self.dataset)
        self.port = QueryDataPort(self.dataset); self.addCleanup(self.port.close)

    def session(self, configured=None, name='run', **options):
        return TaskProgressSession(self.port, configured or plan(), output=self.root / name, **options)

    def test_repeat_read_search_and_continuation_track_only_actual_body(self):
        session = self.session()
        self.assertEqual([r['block_id'] for r in requirement(session.snapshot)['unread_body']], ['b0', 'b1', 'b2'])
        first = session.execute(read_step())
        repeated = session.execute(read_step())
        self.assertEqual(requirement(first['state'])['returned_body'], requirement(repeated['state'])['returned_body'])
        search = session.execute({'task_id': 'business', 'requirement_id': 'body', 'action': 'search_source',
                                  'search': {'source_snapshot_id': 'acme-annual', 'node_id': 'business', 'phrase': 'sales'}})
        self.assertEqual(search['result']['total'], 2)
        self.assertEqual(len(requirement(search['state'])['returned_body']), 1)
        last = session.execute(read_step(cursor=first['result']['next_cursor'], count=2))
        tracked = requirement(last['state'])
        self.assertEqual(len(tracked['returned_body']), 3)
        self.assertEqual(tracked['unread_body'], [])
        self.assertEqual(tracked['completion'], 'not_evaluated')
        self.assertIsNone(tracked['first_unread'])

    def test_end_cursor_does_not_erase_unread_earlier_blocks(self):
        session = self.session()
        last = session.execute(read_step(start_block_id='b2'))
        state = requirement(last['state'])
        self.assertIsNone(state['last_read_cursor'])
        self.assertEqual(state['first_unread']['block_id'], 'b0')
        self.assertEqual([r['block_id'] for r in state['unread_body']], ['b0', 'b1'])

    def test_query_records_are_bound_to_task_and_package_not_read_coverage(self):
        session = self.session()
        queried = session.execute(query_step())
        self.assertEqual(queried['event']['outcome'], 'recorded', queried['event']['error'])
        state = requirement(queried['state'], 'margin', 'margin')
        self.assertEqual(len(state['record_ids']), 2)
        self.assertEqual(len(state['computed_ids']), 1)
        self.assertEqual(queried['result']['computed_facts'][0]['display_decimal'], '15.00')
        self.assertFalse(requirement(queried['state'])['returned_body'])
        aids = {a['artifact_id'] for a in queried['package']['artifacts']}
        self.assertEqual(set(state['artifact_ids']), aids)
        self.assertTrue(state['issues'])  # independent source has missing original quote locators
        repeated = session.execute(query_step())
        self.assertEqual(state['record_ids'], requirement(repeated['state'], 'margin', 'margin')['record_ids'])

    def test_outside_task_source_period_and_unknown_ids_fail_without_progress(self):
        session = self.session()
        wrong_source = read_step(); wrong_source['read']['source_snapshot_id'] = 'acme-amended'
        wrong_task = read_step(); wrong_task['task_id'] = 'missing'
        wrong_node = read_step(); wrong_node['read']['node_id'] = 'risks'
        wrong_period = query_step(); wrong_period['query'] = copy.deepcopy(wrong_period['query'])
        wrong_period['query']['calculations'][0]['periods'] = [year(2030)]
        for action in (wrong_source, wrong_task, wrong_node, wrong_period):
            result = session.execute(action)
            self.assertEqual(result['event']['outcome'], 'error')
            self.assertIsNone(result['result'])
            self.assertFalse(requirement(result['state'])['returned_body'])
        self.assertTrue(requirement(session.snapshot)['issues'])

    def test_colliding_local_ids_in_other_sources_do_not_merge(self):
        configured = plan()
        configured['scope']['source_snapshot_ids'].append('acme-amended')
        other = copy.deepcopy(configured['tasks'][0]); other['task_id'] = 'amended'
        other['source_snapshot_ids'] = ['acme-amended']; other['requirements'][0]['source_snapshot_id'] = 'acme-amended'
        configured['tasks'].append(other)
        session = self.session(configured)
        session.execute(read_step())
        action = read_step(); action['task_id'] = 'amended'; action['read']['source_snapshot_id'] = 'acme-amended'
        current = session.execute(action)['state']
        a = requirement(current)['returned_body'][0]
        b = requirement(current, 'amended')['returned_body'][0]
        self.assertEqual(a['block_id'], b['block_id'])
        self.assertNotEqual(a['source_snapshot_id'], b['source_snapshot_id'])
        self.assertNotEqual(a['index_id'], b['index_id'])
        self.assertEqual(len(requirement(current)['unread_body']), 2)

    def test_missing_node_and_candidate_filter_remain_explicit_unavailable_ranges(self):
        for key in ('node_missing', 'quality_filtered'):
            configured = plan()
            if key == 'node_missing': configured['tasks'][0]['requirements'][0]['node_id'] = 'absent'
            else: configured['scope']['include_candidates'] = False
            session = self.session(configured, name=key)
            state = requirement(session.snapshot)
            self.assertEqual(state['availability'], key)
            self.assertTrue(state['issues'])
            self.assertEqual(state['completion'], 'not_evaluated')

    def test_dependencies_not_yet_implemented_are_not_silently_bypassed(self):
        configured = plan(); configured['tasks'][1]['depends_on'] = ['business']
        session = self.session(configured)
        result = session.execute(query_step())
        self.assertIn('dependency_evaluation_not_implemented', result['event']['error']['detail'])
        self.assertIsNone(result['result'])

    def test_tampered_tool_text_does_not_advance_progress(self):
        session = self.session()
        task_port = session._ports['business']
        original = task_port.read_source(read_step()['read'])
        original['blocks'][0]['text'] = 'Invented replacement'
        with patch.object(task_port, 'read_source', return_value=original):
            result = session.execute(read_step())
        self.assertEqual(result['event']['outcome'], 'error')
        self.assertIsNone(result['package'])
        self.assertFalse(requirement(result['state'])['returned_body'])

    def test_images_are_not_counted_as_read_body(self):
        other = self.root / 'image-dataset'; other.mkdir(); make_scoped_dataset(other)
        folder = other / 'indexes/acme-annual'
        blocks_path = folder / 'blocks.jsonl'
        blocks = [json.loads(line) for line in blocks_path.read_text().splitlines()]
        blocks[2].update(type='image', text='alt', image_asset_id='image-a')
        blocks_path.write_text(''.join(json.dumps(b) + '\n' for b in blocks))
        m = json.loads((folder / 'manifest.json').read_text()); m['artifacts']['blocks.jsonl']['sha256'] = digest(blocks_path.read_bytes())
        (folder / 'manifest.json').write_text(json.dumps(m))
        m = json.loads((other / 'manifest.json').read_text())
        m['files'] = {str(p.relative_to(other)): digest(p.read_bytes()) for p in other.rglob('*') if p.is_file() and p != other / 'manifest.json'}
        (other / 'manifest.json').write_text(json.dumps(m))
        with QueryDataPort(other) as port:
            session = TaskProgressSession(port, plan(), output=self.root / 'images')
            result = session.execute(read_step(start_block_id='b2'))
            self.assertEqual(result['event']['outcome'], 'recorded', result['event']['error'])
            state = requirement(result['state'])
            self.assertEqual(len(state['required_body']), 2)
            self.assertEqual(len(state['unread_body']), 2)
            self.assertEqual(len(state['image_references']), 1)
            self.assertFalse(state['returned_body'])

    def test_snapshot_is_detached_and_step_limits_and_output_immutability_hold(self):
        session = self.session(max_steps=1)
        external = session.snapshot; external['tasks'][0]['requirements'][0]['unread_body'].clear()
        self.assertEqual(len(requirement(session.snapshot)['unread_body']), 3)
        session.execute(read_step())
        with self.assertRaisesRegex(ValueError, 'limit'):
            session.execute(read_step())
        result = session.close()
        self.assertEqual(result['recorded_steps'], 1)
        with self.assertRaises(FileExistsError): self.session()
        with self.assertRaises(RuntimeError): session.execute(read_step())
        with self.assertRaises(ValueError): TaskProgressSession(self.port, plan(), output=self.dataset / 'bad')

    def test_replay_verifies_history_and_produces_identical_progress_without_mutating_dataset(self):
        before = {str(p): p.read_bytes() for p in self.dataset.rglob('*') if p.is_file()}
        session = self.session()
        first = session.execute(read_step())
        session.execute(read_step(cursor=first['result']['next_cursor'], count=2))
        session.execute(query_step())
        expected = session.close()
        manifest = self.root / 'run/manifest.json'
        replay = replay_task_session(self.port, self.root / 'run', output=self.root / 'replay', expected_manifest_sha256=digest(manifest.read_bytes()))
        self.assertEqual(expected, replay)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.dataset.rglob('*') if p.is_file()})
        (self.root / 'run/event-0001/state.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'artifact changed'):
            replay_task_session(self.port, self.root / 'run', output=self.root / 'tampered', expected_manifest_sha256=digest(manifest.read_bytes()))

    def test_persistence_failure_never_publishes_or_advances_event(self):
        session = self.session()
        before = session.snapshot
        with patch('uteki.infrastructure.research_data.task_progress.write_new', side_effect=OSError('disk unavailable')):
            with self.assertRaises(OSError):
                session.execute(read_step())
        self.assertEqual(session.snapshot, before)
        self.assertFalse((self.root / 'run/event-0001').exists())
        with self.assertRaises(RuntimeError):
            session.execute(read_step())
        with self.assertRaises(RuntimeError):
            session.close()

    def test_schemas_are_discoverable_without_changing_frozen_query_contract(self):
        schema = self.port.scoped(plan()['scope']).get_schema()
        self.assertIn('plan', schema['task_contracts'])
        self.assertIn('task_progress', schema['output_contracts'])
        self.assertEqual(schema['schema_version'], 'research-query-v0.3')


class TaskProgressFixtureTests(unittest.TestCase):
    def test_registered_real_fixture_has_readable_inputs_results_and_identical_replay(self):
        from scripts.run_task_progress import ROOT, run_fixture
        spec = ROOT / 'experiments/data_agent_query/task-progress-v1/replay-spec.json'
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'offline'
            result = run_fixture(ROOT, spec, output)
            verification = json.loads((output / 'verification.json').read_text())
            self.assertTrue(verification['dataset_unchanged'])
            self.assertTrue(verification['identical_tool_and_progress_replay'])
            self.assertEqual(verification['model_calls'], 0)
            self.assertEqual(verification['execution_errors'], 0)
            self.assertEqual(result['recorded_steps'], 6)
            states = [json.loads((output / f'session/event-{n:04d}/state.json').read_text()) for n in range(1, 7)]
            progress = [requirement(s, 'business', 'business-body') for s in states]
            self.assertEqual([len(p['returned_body']) for p in progress], [0, 4, 4, 4, 7, 7])
            self.assertEqual(len(progress[-1]['required_body']), 79)
            self.assertEqual(len(progress[-1]['unread_body']), 72)
            self.assertEqual(len(progress[-1]['non_body_blocks']), 1)
            numeric = requirement(states[-1], 'cloud-margin', 'margin-inputs')
            self.assertEqual(len(numeric['record_ids']), 2)
            self.assertEqual(len(numeric['computed_ids']), 1)
            self.assertEqual(result['task_completion'], 'not_evaluated')
            report = (output / 'README.md').read_text()
            for expected in ('Step 6', '请求块数', 'Our mission', '2025-01-01 — 2025-12-31', '23.69', '未读 72'):
                self.assertIn(expected, report)
            self.assertNotIn("{'kind': 'year'", report)
