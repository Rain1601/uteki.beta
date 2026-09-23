"""Host-owned sequential task evidence ledger, with opt-in completion checks.

Task steps carry requests only. Tools execute inside a per-task narrowed scope;
canonical evidence packaging succeeds before any returned data affects progress.
Every committed event contains its inputs, outputs and an immutable state snapshot.
"""
from copy import deepcopy
import json
from pathlib import Path
import tempfile

from uteki.agents.data_query.artifacts import write_new
from uteki.agents.reading.document_reader import DocumentReader
from uteki.domain.research_data.evidence_package import EvidencePackage
from uteki.domain.research_data.task_completion import COMPLETION_VERSION, CompletionAssessment
from uteki.domain.research_data.task_plan import (
    PROGRESS_VERSION, ProgressSnapshot, TaskPlan, TaskStep,
)
from uteki.domain.research_data.query_contract import DataQuery
from .evidence_packaging import build_evidence_package
from .financial_records import digest
from .query_dataset import contained
from .task_completion import TaskCompletionEvaluator


def _unique(values):
    result, seen = [], set()
    for value in values:
        key = digest(value)
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


class TaskProgressSession:
    """Execution facade for caller/scripted task plans, ready for later ReAct use."""

    def __init__(self, port, plan, *, output: Path, max_steps=12, completion_checks=False):
        if type(max_steps) is not int or not 1 <= max_steps <= 64:
            raise ValueError('Task execution limit must be 1..64 steps')
        if type(completion_checks) is not bool:
            raise ValueError('Completion checks must be explicitly enabled with a boolean')
        parsed = TaskPlan.model_validate(plan)
        # Isolate nested QueryPlan dictionaries as well as frozen model fields.
        self._plan = TaskPlan.model_validate(parsed.model_dump(mode='json'))
        self._port = port.scoped(self._plan.scope)
        self._ports, self._tasks, self._inventories = {}, {}, {}
        self._max_steps, self._events, self._closed, self._failed = max_steps, [], False, False
        self._completion_checks, self._receipts = completion_checks, []
        self._output = Path(output).resolve()
        if self._output.is_relative_to(port.dataset):
            raise ValueError('Task outputs must be outside the immutable dataset')
        self._plan_hash = digest(self._plan.model_dump(mode='json'))
        self._source_bytes = self._frozen_json('sources.json')
        if {s['source_snapshot_id']: s for s in self._source_bytes if s['source_snapshot_id'] in self._plan.scope.source_snapshot_ids} != {s['source_snapshot_id']: s for s in self._port.sources}:
            raise ValueError('Task source metadata differs from the frozen dataset')
        tasks = []
        for task in self._plan.tasks:
            self._tasks[task.task_id] = task
            companies = sorted({s['company_id'] for s in self._port.sources if s['source_snapshot_id'] in task.source_snapshot_ids})
            scope = self._plan.scope.model_dump(mode='json')
            scope.update(company_ids=companies, source_snapshot_ids=list(task.source_snapshot_ids))
            task_port = self._port.scoped(scope)
            self._ports[task.task_id] = task_port
            requirements = []
            for requirement in task.requirements:
                state = dict(requirement_id=requirement.requirement_id, kind=requirement.kind,
                             availability='not_queried', events=[], issues=[], required_body=[], returned_body=[],
                             unread_body=[], image_references=[], non_body_blocks=[], context_ids=[], artifact_ids=[],
                             record_ids=[], computed_ids=[], last_read_cursor=None, first_unread=None,
                             observed_query_status=None, query_selections=[], completion='not_evaluated')
                if requirement.kind == 'read_node':
                    inventory = self._inventory(task_port, requirement)
                    self._inventories[(task.task_id, requirement.requirement_id)] = inventory
                    state.update(availability=inventory['status'], required_body=inventory['body'],
                                 unread_body=inventory['body'], first_unread=next(iter(inventory['body']), None))
                    if inventory['status'] != 'available':
                        state['issues'].append({'sequence': 0, 'origin': 'binding', 'reason': inventory['status']})
                elif requirement.kind == 'query':
                    state['availability'] = 'not_applicable'
                    query = requirement.query
                    if any(r.entity_id not in task_port.entities for r in (*query.records, *query.calculations)):
                        raise ValueError('Task query entity is outside its source scope')
                else:
                    state.update(availability='clarification_required', issues=[{
                        'sequence': 0, 'origin': 'plan', 'reason': 'clarification_required', 'question': requirement.question}])
                requirements.append(state)
            tasks.append({'task_id': task.task_id, 'requirements': requirements, 'completion': 'not_evaluated'})
        self._state = ProgressSnapshot(plan_id=self._plan.plan_id, plan_sha256=self._plan_hash,
            snapshot_id=port.snapshot_id, sequence=0, tasks=tasks).model_dump(mode='json')
        self._evaluator = TaskCompletionEvaluator(self._plan, self._inventories) if completion_checks else None
        self._completion = self._evaluate(self._state, []) if completion_checks else None
        self._output.mkdir(parents=True, exist_ok=False)
        write_new(self._output / 'plan.json', self._plan.model_dump(mode='json'))
        write_new(self._output / 'plan.schema.json', TaskPlan.model_json_schema())
        write_new(self._output / 'step.schema.json', TaskStep.model_json_schema())
        write_new(self._output / 'progress.schema.json', ProgressSnapshot.model_json_schema())
        write_new(self._output / 'initial-state.json', self._state)
        config = {'max_steps': max_steps,
            'execution_mode': 'explicit_task_steps', 'model_calls': 0,
            'plan_sha256': self._plan_hash, 'dataset_manifest_sha256': digest((port.dataset / 'manifest.json').read_bytes())}
        if completion_checks:
            config['completion_rules_version'] = COMPLETION_VERSION
            write_new(self._output / 'completion.schema.json', CompletionAssessment.model_json_schema())
            write_new(self._output / 'initial-completion.json', self._completion)
        write_new(self._output / 'config.json', config)

    def _frozen_json(self, name):
        expected = self._port.manifest['files'].get(name)
        data = contained(self._port.dataset, name).read_bytes()
        if expected is None or digest(data) != expected:
            raise ValueError('Task inventory input is not the frozen artifact')
        return json.loads(data)

    def _inventory(self, port, requirement):
        source = next(s for s in port.sources if s['source_snapshot_id'] == requirement.source_snapshot_id)
        if not port.scope.include_candidates:
            return {'status': 'quality_filtered', 'body': [], 'blocks': {}}
        if source['available_at'] > str(port.scope.knowledge_cutoff):
            return {'status': 'not_available_at_cutoff', 'body': [], 'blocks': {}}
        folder = source.get('index_folder')
        if not folder:
            return {'status': 'index_missing', 'body': [], 'blocks': {}}
        for name in ('manifest.json', 'index.json', 'blocks.jsonl'):
            relative = folder + '/' + name
            data = contained(port.dataset, relative).read_bytes()
            if digest(data) != port.manifest['files'].get(relative):
                raise ValueError('Task inventory source/index hash mismatch')
        reader = DocumentReader(contained(port.dataset, folder))
        if reader.index['index_id'] != source['index_id']:
            raise ValueError('Task inventory index identity mismatch')
        if requirement.node_id not in reader.nodes:
            return {'status': 'node_missing', 'body': [], 'blocks': {}}
        lo, hi = reader._range(requirement.node_id)
        blocks, body = {}, []
        for block in reader.blocks[lo:hi]:
            ref = {'snapshot_id': port.snapshot_id, 'source_snapshot_id': source['source_snapshot_id'],
                   'index_id': source['index_id'], 'block_id': block['block_id']}
            mode = 'image' if block['type'] == 'image' else 'non_body' if block.get('layout_role') or block['type'] == 'page_marker' else 'body'
            blocks[block['block_id']] = {'ref': ref, 'mode': mode}
            if mode == 'body':
                body.append(ref)
        return {'status': 'available', 'body': body, 'blocks': blocks}

    @property
    def snapshot(self):
        return deepcopy(self._state)

    def _evaluate(self, state, receipts):
        return self._evaluator.evaluate(state, receipts, step_limit=self._max_steps)

    def check_completion(self):
        """Read-only finish readiness; does not close, advance or reset a session."""
        if self._failed:
            raise RuntimeError('Task session persistence failed')
        if not self._completion_checks:
            raise ValueError('Completion checks require an explicitly enabled new run')
        return deepcopy(self._completion)

    def _guard(self, step):
        task = self._tasks.get(step.task_id)
        if task is None:
            raise ValueError('Unknown task ID')
        requirement = next((r for r in task.requirements if r.requirement_id == step.requirement_id), None)
        if requirement is None:
            raise ValueError('Unknown requirement ID for task')
        if task.depends_on:
            if not self._completion_checks:
                raise ValueError('dependency_evaluation_not_implemented; dependent task cannot execute yet')
            current = {t['task_id']: t['status'] for t in self._completion['tasks']}
            unmet = [key for key in task.depends_on if current[key] != 'satisfied']
            if unmet:
                raise ValueError('dependency_unsatisfied: ' + ', '.join(unmet))
        if requirement.kind == 'clarification':
            raise ValueError('caller_clarification_required; plan revision support is not implemented')
        if step.action == 'query':
            if requirement.kind != 'query' or step.query != requirement.query:
                raise ValueError('Query differs from the declared task requirement')
        else:
            payload = {'outline_source': step.outline, 'read_source': step.read, 'search_source': step.search}[step.action]
            if requirement.kind != 'read_node' or payload.source_snapshot_id != requirement.source_snapshot_id:
                raise ValueError('Navigation differs from the declared task source')
            if step.action != 'outline_source' and payload.node_id != requirement.node_id:
                raise ValueError('Navigation differs from the declared task node')
        return self._ports[task.task_id], requirement

    def _execute(self, step, port, sequence):
        if step.action == 'query':
            scope = port.scope
            return port.query_data(DataQuery(query_id=f'task-step-{sequence}', question=self._plan.question,
                snapshot_id=scope.snapshot_id, source_policy_id=scope.source_policy_id,
                knowledge_cutoff=scope.knowledge_cutoff, include_candidates=scope.include_candidates,
                **step.query.model_dump()))
        return getattr(port, step.action)({'outline_source': step.outline,
                                          'read_source': step.read, 'search_source': step.search}[step.action])

    def _package(self, step, port, value):
        if value.get('scope') != port.scope.model_dump(mode='json') or value.get('scope_id') != port.scope_id:
            raise ValueError('Tool result scope differs from its task')
        if step.action != 'query':
            request = {'outline_source': step.outline, 'read_source': step.read, 'search_source': step.search}[step.action]
            if value.get('source_snapshot_id') != request.source_snapshot_id:
                raise ValueError('Tool result differs from the requested source')
            if step.action != 'outline_source' and value.get('node_id') != request.node_id:
                raise ValueError('Tool result differs from the requested node')
        result = {'request': {'question': self._plan.question, 'scope': port.scope.model_dump(mode='json')},
                  'records': [], 'computed_facts': [], 'contexts': [], 'evidence': {},
                  'navigation': [], 'gaps': value.get('gaps', [])}
        if step.action == 'query':
            for key in ('records', 'computed_facts', 'evidence'):
                result[key] = value[key]
        elif step.action == 'read_source' and value.get('blocks'):
            cid = 'ctx-' + digest([value['source_snapshot_id'], value['block_ids'], value['blocks']])[:24]
            result['contexts'] = [{'context_id': cid, **value}]
        elif step.action in ('outline_source', 'search_source'):
            result['navigation'] = [{'tool': step.action, **value}]
        return build_evidence_package(port, result)

    def _advance(self, step, value, package, error, sequence):
        state = deepcopy(self._state)
        state['sequence'] = sequence
        task = next((t for t in state['tasks'] if t['task_id'] == step.task_id), None)
        target = next((r for r in task['requirements'] if r['requirement_id'] == step.requirement_id), None) if task else None
        if target is None:
            return ProgressSnapshot.model_validate(state).model_dump(mode='json')
        target['events'].append(sequence)
        if error:
            target['issues'].append({'sequence': sequence, 'origin': 'execution', **error})
            return ProgressSnapshot.model_validate(state).model_dump(mode='json')
        target['artifact_ids'] = _unique([*target['artifact_ids'], *[a['artifact_id'] for a in package['artifacts']]])
        for origin, gaps in (('tool', value.get('gaps', [])), ('evidence_package', package['gaps'])):
            target['issues'].extend({'sequence': sequence, 'origin': origin, **gap} for gap in gaps)
        if step.action == 'read_source' and value.get('status') == 'read':
            inventory = self._inventories[(step.task_id, step.requirement_id)]
            groups = {'body': 'returned_body', 'image': 'image_references', 'non_body': 'non_body_blocks'}
            for block in value['blocks']:
                entry = inventory['blocks'][block['block_id']]
                field = groups[entry['mode']]
                target[field] = _unique([*target[field], entry['ref']])
            seen = {digest(ref) for ref in target['returned_body']}
            target['unread_body'] = [ref for ref in target['required_body'] if digest(ref) not in seen]
            target['first_unread'] = next(iter(target['unread_body']), None)
            target['last_read_cursor'] = value['next_cursor']
            target['context_ids'] = _unique([*target['context_ids'], *[key.removeprefix('context:') for key in package['bindings'] if key.startswith('context:')]])
        if step.action == 'query':
            target['observed_query_status'] = value['status']
            target['query_selections'] = value['selections']
            target['record_ids'] = _unique([*target['record_ids'], *[r['record_id'] for r in value['records']]])
            target['computed_ids'] = _unique([*target['computed_ids'], *[f['computed_id'] for f in value['computed_facts']]])
        return ProgressSnapshot.model_validate(state).model_dump(mode='json')

    def execute(self, request):
        if self._closed or self._failed:
            raise RuntimeError('Task session is closed or its persistence failed')
        if len(self._events) >= self._max_steps:
            raise ValueError('Task step limit reached; no tool executed')
        step = TaskStep.model_validate(request)
        sequence = len(self._events) + 1
        value = package = error = None
        try:
            port, _ = self._guard(step)
            value = self._execute(step, port, sequence)
            package = self._package(step, port, value)
            next_state = self._advance(step, value, package, None, sequence)
        except Exception as exc:
            # Fail closed: errors are retained; no returned evidence advances state.
            error = {'reason': type(exc).__name__, 'detail': str(exc) if isinstance(exc, (ValueError, KeyError, PermissionError)) else 'Tool execution failed'}
            package = None
            next_state = self._advance(step, None, None, error, sequence)
        event = {'schema_version': 'retrieval-task-event-v1', 'sequence': sequence,
                 'task_id': step.task_id, 'requirement_id': step.requirement_id, 'action': step.action,
                 'outcome': 'error' if error else 'recorded', 'plan_sha256': self._plan_hash,
                 'previous_event_sha256': digest(self._events[-1]) if self._events else None,
                 'request_sha256': digest(step.model_dump(mode='json')), 'state_sha256': digest(next_state),
                 'tool_result_sha256': digest(value) if value is not None else None,
                 'evidence_package_sha256': digest(package) if package is not None else None,
                 'error': error}
        try:
            receipts = self._receipts
            if self._completion_checks:
                if package is not None:
                    receipts = [*receipts, deepcopy({'sequence': sequence, 'request': step.model_dump(mode='json'),
                                                    'result': value, 'package': package})]
                completion = self._evaluate(next_state, receipts)
                event['completion_sha256'] = digest(completion)
            staging = Path(tempfile.mkdtemp(prefix='.pending-', dir=self._output))
            write_new(staging / 'request.json', step.model_dump(mode='json'))
            if value is not None:
                write_new(staging / 'tool-result.json', value)
            if package is not None:
                write_new(staging / 'evidence-package.json', package)
            write_new(staging / 'event.json', event)
            write_new(staging / 'state.json', next_state)
            if self._completion_checks:
                write_new(staging / 'completion.json', completion)
            destination = self._output / f'event-{sequence:04d}'
            if destination.exists():
                raise FileExistsError('Task event already exists')
            staging.rename(destination)
        except Exception:
            self._failed = True
            raise
        self._events.append(event)
        self._state = next_state
        result = {'event': event, 'result': value, 'package': package, 'state': next_state}
        if self._completion_checks:
            self._receipts, self._completion = receipts, completion
            result['completion'] = completion
        return deepcopy(result)

    def close(self):
        if self._closed or self._failed:
            raise RuntimeError('Task session is closed or its persistence failed')
        self._closed = True
        result = {'schema_version': PROGRESS_VERSION, 'plan_id': self._plan.plan_id,
                  'recorded_steps': len(self._events), 'step_limit': self._max_steps,
                  'task_completion': 'not_evaluated', 'semantic_completeness': 'not_evaluated',
                  'model_calls': 0, 'state': self.snapshot, 'events': deepcopy(self._events)}
        if self._completion_checks:
            result.update(schema_version='retrieval-task-result-v2', task_completion=self._completion['status'],
                          completion=self.check_completion())
        write_new(self._output / 'result.json', result)
        write_new(self._output / 'evidence-package.schema.json', EvidencePackage.model_json_schema())
        write_new(self._output / 'manifest.json', {'schema_version': 'retrieval-task-run-v1',
            'files': {str(p.relative_to(self._output)): digest(p.read_bytes()) for p in sorted(self._output.rglob('*')) if p.is_file()}})
        return deepcopy(result)


def replay_task_session(port, saved_run, *, output, expected_manifest_sha256):
    """Rerun pinned requests on the same frozen dataset with no planner/model.

    This is tool reproducibility verification, not a way to resume/reset a model
    budget. The same recorded step limit applies; the original run is never edited.
    """
    saved_run = Path(saved_run)
    manifest_bytes = (saved_run / 'manifest.json').read_bytes()
    if digest(manifest_bytes) != expected_manifest_sha256:
        raise ValueError('Saved task manifest changed')
    manifest = json.loads(manifest_bytes)
    files = {}
    for name, expected in manifest['files'].items():
        content = contained(saved_run, name).read_bytes()
        if digest(content) != expected:
            raise ValueError('Saved task artifact changed')
        files[name] = json.loads(content)
    if digest((port.dataset / 'manifest.json').read_bytes()) != files['config.json']['dataset_manifest_sha256']:
        raise ValueError('Replay dataset differs from the original')
    destination = Path(output).resolve()
    if destination == saved_run.resolve() or destination.is_relative_to(saved_run.resolve()):
        raise ValueError('Replay output cannot be inside the saved run')
    version = files['config.json'].get('completion_rules_version')
    if version not in (None, COMPLETION_VERSION):
        raise ValueError('Unsupported completion rules for replay')
    checked = version is not None
    session = TaskProgressSession(port, files['plan.json'], output=destination, max_steps=files['config.json']['max_steps'],
                                  completion_checks=checked)
    if session.snapshot != files['initial-state.json']:
        raise ValueError('Initial progress replay mismatch')
    if checked and session.check_completion() != files['initial-completion.json']:
        raise ValueError('Initial completion replay mismatch')
    for sequence in range(1, files['result.json']['recorded_steps'] + 1):
        prefix = f'event-{sequence:04d}/'
        replayed = session.execute(files[prefix + 'request.json'])
        for key, filename in (('event', 'event.json'), ('state', 'state.json'), ('result', 'tool-result.json'), ('package', 'evidence-package.json')):
            if replayed[key] != files.get(prefix + filename):
                raise ValueError('Task replay mismatch: ' + prefix + filename)
        if checked and replayed['completion'] != files[prefix + 'completion.json']:
            raise ValueError('Completion replay mismatch: ' + prefix)
    result = session.close()
    if result != files['result.json']:
        raise ValueError('Final progress replay mismatch')
    return result
