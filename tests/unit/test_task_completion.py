"""Completion is derived from host evidence, never a model's finish claim."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import duckdb
from pydantic import ValidationError

from scripts.run_task_progress import ROOT, run_fixture
from uteki.domain.research_data.task_completion import CompletionAssessment
from uteki.infrastructure.research_data.financial_records import digest
from uteki.infrastructure.research_data.query_service import QueryDataPort
from uteki.infrastructure.research_data.task_progress import TaskProgressSession, replay_task_session
from tests.unit.test_scoped_query_service import make_scoped_dataset, year
from tests.unit.test_task_progress import plan, read_step, query_step, requirement


def task(assessment, task_id='business'):
    return next(t for t in assessment['tasks'] if t['task_id'] == task_id)


def reasons(assessment, task_id):
    return {c['reason'] for r in task(assessment, task_id)['requirements'] for c in r['checks']}


def pin_dataset(folder):
    manifest_path = folder / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['files'] = {str(p.relative_to(folder)): digest(p.read_bytes())
                         for p in folder.rglob('*') if p.is_file() and p != manifest_path}
    manifest_path.write_text(json.dumps(manifest))


def attach_synthetic_quotes(folder):
    """Explicit fixture only: attach each invented record to its invented text."""
    db = duckdb.connect(str(folder / 'research.duckdb'))
    for sid, in db.execute('SELECT source_snapshot_id FROM sources').fetchall():
        index = folder / 'indexes' / sid
        path = index / 'blocks.jsonl'
        blocks = [json.loads(line) for line in path.read_text().splitlines()]
        for payload, in db.execute('SELECT payload FROM observations WHERE source_snapshot_id = ?', [sid]).fetchall():
            record = json.loads(payload)
            quote = f"{record['entity_id']} {record['metric_id']} {record['period']['end']}: {record['value_decimal']} USD."
            blocks[9]['text'] += '\n' + quote
            evidence = {'evidence_id': record['record_id'], 'source_snapshot_id': sid, 'block_id': 'b9', 'quote': quote}
            db.execute('UPDATE evidence SET payload = ? WHERE evidence_id = ?', [json.dumps(evidence), record['record_id']])
        path.write_text(''.join(json.dumps(b) + '\n' for b in blocks))
        manifest = json.loads((index / 'manifest.json').read_text())
        manifest['artifacts']['blocks.jsonl']['sha256'] = digest(path.read_bytes())
        (index / 'manifest.json').write_text(json.dumps(manifest))
    db.close()
    pin_dataset(folder)


class TaskCompletionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.dataset = self.root / 'dataset'; self.dataset.mkdir()
        make_scoped_dataset(self.dataset)

    def session(self, configured=None, *, citations=True, name='run', max_steps=12):
        if citations:
            attach_synthetic_quotes(self.dataset)
        port = QueryDataPort(self.dataset); self.addCleanup(port.close)
        self.port = port
        return TaskProgressSession(port, configured or plan(), output=self.root / name,
                                   max_steps=max_steps, completion_checks=True)

    def test_partial_repeat_search_and_end_cursor_do_not_satisfy_read_requirement(self):
        session = self.session()
        last = session.execute(read_step(start_block_id='b2'))
        self.assertIsNone(last['result']['next_cursor'])
        self.assertEqual(task(last['completion'])['status'], 'missing_evidence')
        for _ in range(2): session.execute(read_step(start_block_id='b2'))
        session.execute({'task_id': 'business', 'requirement_id': 'body', 'action': 'search_source',
            'search': {'source_snapshot_id': 'acme-annual', 'node_id': 'business', 'phrase': 'sales'}})
        self.assertEqual(len(requirement(session.snapshot)['unread_body']), 2)
        self.assertFalse(session.check_completion()['finish_allowed'])

    def test_read_and_cited_query_satisfy_only_engineering_conditions_even_at_limit(self):
        session = self.session(max_steps=2)
        session.execute(read_step(count=3))
        result = session.execute(query_step())
        verdict = result['completion']
        self.assertEqual(verdict['status'], 'satisfied')
        self.assertEqual(verdict['steps_remaining'], 0)
        self.assertTrue(verdict['finish_allowed'])
        self.assertEqual(verdict['semantic_completeness'], 'not_evaluated')
        self.assertIn('source_citations_verified', reasons(verdict, 'margin'))
        self.assertIn('calculation_verified', reasons(verdict, 'margin'))
        self.assertTrue(task(verdict, 'margin')['requirements'][0]['retained_issues'])  # unknown normalization origin
        self.assertEqual(session.close()['task_completion'], 'satisfied')

    def test_successful_sql_without_original_quote_does_not_satisfy_query(self):
        session = self.session(citations=False)
        result = session.execute(query_step())
        self.assertEqual(result['result']['status'], 'complete')
        self.assertEqual(task(result['completion'], 'margin')['status'], 'missing_evidence')
        self.assertIn('source_citation_missing', reasons(result['completion'], 'margin'))
        self.assertIn('calculation_verified', reasons(result['completion'], 'margin'))

    def test_duplicate_calculation_requests_do_not_create_duplicate_conditions(self):
        configured = plan()
        query = configured['tasks'][1]['requirements'][0]['query']
        query['calculations'] *= 2
        session = self.session(configured)
        action = query_step(); action['query'] = query
        result = session.execute(action)
        self.assertEqual(task(result['completion'], 'margin')['status'], 'satisfied')
        checks = task(result['completion'], 'margin')['requirements'][0]['checks']
        self.assertEqual(sum(c['reason'] == 'calculation_verified' for c in checks), 1)

    def test_record_only_requirements_work_for_other_company_and_period(self):
        attach_synthetic_quotes(self.dataset)
        for company, sid, entity, period in [('acme', 'acme-annual', 'acme-services', 2030),
                                               ('other', 'other-annual', 'other-services', 2031)]:
            configured = plan()
            configured['question'] = f'Retrieve revenue for FY{period}.'
            configured['scope'].update(company_ids=[company], source_snapshot_ids=[sid])
            configured['tasks'] = configured['tasks'][1:]
            configured['tasks'][0]['source_snapshot_ids'] = [sid]
            query = {'records': [{'entity_id': entity, 'metric_id': 'revenue', 'period': year(period)}]}
            configured['tasks'][0]['requirements'][0]['query'] = query
            session = self.session(configured, citations=False, name=company)
            action = query_step(); action['query'] = query
            result = session.execute(action)
            self.assertEqual(result['completion']['status'], 'satisfied')
            self.assertEqual({r['source_snapshot_id'] for r in result['result']['records']}, {sid})

    def test_dependency_refuses_execution_then_allows_after_actual_parent_satisfied(self):
        configured = plan(); configured['tasks'][1]['depends_on'] = ['business']
        session = self.session(configured)
        first = session.execute(query_step())
        self.assertIsNone(first['result'])
        self.assertIn('dependency_unsatisfied', first['event']['error']['detail'])
        self.assertEqual(task(first['completion'], 'margin')['status'], 'blocked')
        session.execute(read_step(count=3))
        final = session.execute(query_step())
        self.assertEqual(final['completion']['status'], 'satisfied')
        self.assertTrue(task(final['completion'], 'margin')['requirements'][0]['retained_issues'])

    def test_finish_readiness_is_read_only_and_cannot_skip_requirements(self):
        session = self.session()
        before = session.snapshot
        result = session.check_completion()
        self.assertFalse(result['finish_allowed'])
        result['tasks'].clear(); result['finish_allowed'] = True
        self.assertEqual(session.snapshot, before)
        self.assertFalse(session.check_completion()['finish_allowed'])
        session.execute(read_step(count=3))
        self.assertFalse(session.check_completion()['finish_allowed'])
        session.execute(query_step())
        self.assertTrue(session.check_completion()['finish_allowed'])

    def test_limit_preserves_missing_condition_and_prevents_more_execution(self):
        session = self.session(max_steps=1)
        session.execute(read_step())
        verdict = session.check_completion()
        self.assertEqual(verdict['status'], 'limited')
        self.assertEqual(verdict['conditions_status'], 'missing_evidence')
        self.assertFalse(verdict['finish_allowed'])
        with self.assertRaisesRegex(ValueError, 'limit'): session.execute(query_step())
        self.assertEqual(session.close()['completion'], verdict)

    def test_missing_node_and_quality_filter_do_not_pass_vacuously(self):
        configured = plan(); configured['tasks'][0]['requirements'][0]['node_id'] = 'absent'
        session = self.session(configured)
        self.assertEqual(task(session.check_completion())['status'], 'blocked')
        self.assertIn('node_missing', reasons(session.check_completion(), 'business'))
        configured = plan(); configured['scope']['include_candidates'] = False
        filtered = self.session(configured, citations=False, name='filtered')
        self.assertEqual(task(filtered.check_completion())['status'], 'blocked')
        self.assertIn('quality_filtered', reasons(filtered.check_completion(), 'business'))

    def test_clarification_is_explicitly_blocked(self):
        configured = plan()
        configured['tasks'][1]['requirements'] = [{'kind': 'clarification', 'requirement_id': 'period', 'question': 'Which year?'}]
        session = self.session(configured)
        self.assertEqual(task(session.check_completion(), 'margin')['status'], 'blocked')
        self.assertIn('caller_clarification_required', reasons(session.check_completion(), 'margin'))

    def test_image_only_range_cannot_satisfy_body_requirement(self):
        path = self.dataset / 'indexes/acme-annual/blocks.jsonl'
        blocks = [json.loads(line) for line in path.read_text().splitlines()]
        for block in blocks[:3]: block['type'] = 'image'
        path.write_text(''.join(json.dumps(b) + '\n' for b in blocks))
        session = self.session()  # pins this independent fixture, including index hashes
        self.assertIn('no_body_blocks', reasons(session.check_completion(), 'business'))
        self.assertEqual(task(session.check_completion())['status'], 'blocked')

    def test_primary_quote_present_but_qualifier_quote_missing_fails(self):
        attach_synthetic_quotes(self.dataset)
        db = duckdb.connect(str(self.dataset / 'research.duckdb'))
        rid = 'acme-annual-revenue-2031'
        record = json.loads(db.execute('SELECT payload FROM observations WHERE record_id = ?', [rid]).fetchone()[0])
        record['qualifier_evidence_ids'] = ['qualifier-missing']
        db.execute('UPDATE observations SET payload = ? WHERE record_id = ?', [json.dumps(record), rid])
        db.execute('INSERT INTO evidence VALUES (?, ?, ?)', ['qualifier-missing', 'acme-annual', json.dumps({
            'evidence_id': 'qualifier-missing', 'source_snapshot_id': 'acme-annual', 'quote': 'Unlocated qualification'})])
        db.close(); pin_dataset(self.dataset)
        session = self.session(citations=False)
        result = session.execute(query_step())
        self.assertEqual(result['event']['outcome'], 'recorded')
        self.assertIn('source_citation_missing', reasons(result['completion'], 'margin'))
        self.assertEqual(task(result['completion'], 'margin')['status'], 'missing_evidence')

    def test_same_block_ids_from_another_task_source_cannot_satisfy_its_requirement(self):
        configured = plan(); configured['scope']['source_snapshot_ids'].append('acme-amended')
        other = copy.deepcopy(configured['tasks'][0]); other['task_id'] = 'amended'
        other['source_snapshot_ids'] = ['acme-amended']
        other['requirements'][0]['source_snapshot_id'] = 'acme-amended'
        configured['tasks'].append(other)
        session = self.session(configured)
        result = session.execute(read_step(count=3))
        self.assertEqual(task(result['completion'])['status'], 'satisfied')
        self.assertEqual(task(result['completion'], 'amended')['status'], 'missing_evidence')

    def test_tampered_progress_or_removed_requirement_is_rejected(self):
        session = self.session()
        fake = session.snapshot
        fake['tasks'][0]['requirements'][0]['returned_body'] = copy.deepcopy(fake['tasks'][0]['requirements'][0]['required_body'])
        fake['tasks'][0]['requirements'][0]['unread_body'] = []
        with self.assertRaisesRegex(ValueError, 'actual verified receipts'):
            session._evaluator.evaluate(fake, [], step_limit=12)
        fake = session.snapshot; fake['tasks'].pop()
        with self.assertRaisesRegex(ValueError, 'omit'):
            session._evaluator.evaluate(fake, [], step_limit=12)

    def test_tampered_tool_result_cannot_increase_completion(self):
        session = self.session()
        task_port = session._ports['business']
        value = task_port.read_source(read_step()['read'])
        value['blocks'][0]['text'] = 'Invented'
        with patch.object(task_port, 'read_source', return_value=value): result = session.execute(read_step())
        self.assertEqual(result['event']['outcome'], 'error')
        self.assertFalse(result['completion']['finish_allowed'])
        self.assertEqual(task(result['completion'])['status'], 'missing_evidence')

    def test_assessment_persistence_failure_does_not_publish_event_or_update_state(self):
        from uteki.infrastructure.research_data.task_progress import write_new
        session = self.session()
        before = session.snapshot
        def fail_assessment(path, value):
            if path.name == 'completion.json': raise OSError('unavailable')
            write_new(path, value)
        with patch('uteki.infrastructure.research_data.task_progress.write_new', side_effect=fail_assessment):
            with self.assertRaises(OSError): session.execute(read_step())
        self.assertEqual(session.snapshot, before)
        self.assertFalse((self.root / 'run/event-0001').exists())
        with self.assertRaises(RuntimeError): session.check_completion()

    def test_record_for_another_period_cannot_satisfy_request(self):
        session = self.session()
        result = session.execute(query_step())
        receipt = copy.deepcopy(session._receipts[0])
        receipt['result']['records'][0]['period'] = year(2030)
        verdict = session._evaluator.evaluate(result['state'], [receipt], step_limit=12)
        self.assertFalse(verdict['finish_allowed'])
        self.assertIn('record_mismatch', reasons(verdict, 'margin'))

    def test_wrong_source_and_node_do_not_unlock_dependent_task(self):
        configured = plan(); configured['tasks'][1]['depends_on'] = ['business']
        session = self.session(configured)
        wrong = read_step(); wrong['read']['source_snapshot_id'] = 'other-annual'
        result = session.execute(wrong)
        self.assertEqual(result['event']['outcome'], 'error')
        self.assertEqual(task(result['completion'], 'margin')['status'], 'blocked')
        wrong = read_step(); wrong['read']['node_id'] = 'risks'
        result = session.execute(wrong)
        self.assertEqual(result['event']['outcome'], 'error')
        self.assertFalse(result['completion']['finish_allowed'])

    def test_ambiguous_records_and_missing_calculation_do_not_pass(self):
        configured = plan()
        configured['scope']['source_snapshot_ids'].append('acme-amended')
        configured['tasks'][1]['source_snapshot_ids'].append('acme-amended')
        session = self.session(configured)
        result = session.execute(query_step())
        self.assertEqual(task(result['completion'], 'margin')['status'], 'blocked')
        self.assertIn('record_ambiguous', reasons(result['completion'], 'margin'))
        self.assertIn('calculation_or_operands_missing', reasons(result['completion'], 'margin'))

    def test_completion_and_legacy_sessions_replay_without_rewriting_history(self):
        session = self.session()
        session.execute(read_step(count=3)); session.execute(query_step())
        expected = session.close()
        saved = self.root / 'run'
        before = {str(p): p.read_bytes() for p in saved.rglob('*') if p.is_file()}
        manifest = digest((saved / 'manifest.json').read_bytes())
        actual = replay_task_session(self.port, saved, output=self.root / 'replay', expected_manifest_sha256=manifest)
        self.assertEqual(expected, actual)
        self.assertEqual(before, {str(p): p.read_bytes() for p in saved.rglob('*') if p.is_file()})
        (saved / 'event-0001/completion.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'artifact changed'):
            replay_task_session(self.port, saved, output=self.root / 'bad', expected_manifest_sha256=manifest)

    def test_schema_exposes_assessment_separately_from_model_actions(self):
        session = self.session()
        schema = self.port.scoped(plan()['scope']).get_schema()
        self.assertIn('task_completion', schema['output_contracts'])
        self.assertNotIn('task_completion', schema['execution_contracts'])
        CompletionAssessment.model_validate(session.check_completion())

    def test_schema_rejects_inconsistent_finish_and_budget_claims(self):
        session = self.session()
        for change in ({'finish_allowed': True}, {'status': 'satisfied'}, {'steps_remaining': 100}):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                CompletionAssessment.model_validate({**session.check_completion(), **change})


class TaskCompletionRealFixtureTests(unittest.TestCase):
    def test_real_six_step_report_and_old_frozen_run_remain_reproducible(self):
        spec = ROOT / 'experiments/data_agent_query/task-completion-v1/replay-spec.json'
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'run'
            result = run_fixture(ROOT, spec, output)
            verdict = result['completion']
            self.assertEqual(result['task_completion'], 'limited')
            self.assertEqual(task(verdict)['status'], 'missing_evidence')
            self.assertEqual(task(verdict, 'cloud-margin')['status'], 'satisfied')
            self.assertEqual(task(verdict)['requirements'][0]['checks'][1]['remaining_count'], 72)
            text = (output / 'README.md').read_text()
            for expected in ('仍缺 72 块', '取证条件满足', '达到步数上限', '语义充分性未评估'):
                self.assertIn(expected, text)
            verification = json.loads((output / 'verification.json').read_text())
            self.assertTrue(verification['dataset_unchanged'])
            self.assertTrue(verification['identical_tool_and_progress_replay'])
            old = ROOT / 'experiments/data_agent_query/task-progress-v1/offline-01/session'
            dataset = ROOT / json.loads(spec.read_text())['dataset']
            with QueryDataPort(dataset) as port:
                legacy = replay_task_session(port, old, output=Path(temp) / 'legacy',
                    expected_manifest_sha256=digest((old / 'manifest.json').read_bytes()))
            self.assertEqual(legacy['task_completion'], 'not_evaluated')
