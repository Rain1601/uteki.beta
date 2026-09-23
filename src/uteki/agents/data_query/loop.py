"""Small bounded planner loop over the existing task session; with a bounded question-to-plan proposal."""
import asyncio
from copy import deepcopy
import json
import logging
from pathlib import Path

from pydantic import ValidationError

from uteki.domain.research_data.task_plan import TaskPlan, TaskPlannerDecision, TaskPlanProposal
from uteki.domain.research_data.scoped_agent_query import ScopedAgentQuery
from uteki.domain.research_data.period_scope import explicit_periods
from uteki.infrastructure.research_data.task_progress import TaskProgressSession
from uteki.infrastructure.research_data.financial_records import digest
from .agent import DataQueryAgent
from .artifacts import write_new

logger = logging.getLogger(__name__)


async def run_question_loop(agent, request, *, output):
    """One bounded proposal call followed by the existing task loop; same budget."""
    request = ScopedAgentQuery.model_validate(request)
    plan_origin = getattr(agent.planner, "plan_origin", None)
    if plan_origin not in ("model", "scripted_fixture"):
        raise ValueError("Question planner must declare plan_origin as model or scripted_fixture")
    scoped = agent.port.scoped(request.scope)
    output = Path(output).resolve()
    if output.is_relative_to(agent.port.dataset):
        raise ValueError('Question output must be outside the frozen dataset')
    schema, discovery = scoped.get_schema(), scoped.discover_data()
    outlines = []
    for sid in request.scope.source_snapshot_ids:
        try:
            outlines.append(scoped.outline_source({'source_snapshot_id': sid}))
        except (ValueError, KeyError, FileNotFoundError):
            outlines.append({'source_snapshot_id': sid, 'status': 'outline_unavailable'})
    packet = {'request': request.model_dump(mode='json'), 'catalog': {
        'entities': schema['entities'], 'metrics': schema['metrics'], 'sources': discovery['sources'],
        'coverage': discovery['coverage'], 'outlines': outlines,
        'explicit_periods': [p.model_dump(mode='json') for p in explicit_periods(request.question)]}}
    output.mkdir(parents=True, exist_ok=False)
    write_new(output / 'request.json', request.model_dump(mode='json'))
    result = {'status': 'limited', 'stop_reason': 'context_budget_exceeded', 'planning_calls': 0,
              'request': request.model_dump(mode='json'), 'semantic_completeness': 'not_evaluated'}
    if len(json.dumps(packet, ensure_ascii=False).encode()) <= agent.max_packet_bytes:
        write_new(output / 'planning-input.json', packet)
        result['planning_calls'] = 1
        logger.info('自动拆题：等待模型返回任务计划')
        try:
            raw = await asyncio.wait_for(agent.planner.draft_plan(deepcopy(packet)), timeout=agent.turn_timeout)
            proposal = TaskPlanProposal.model_validate(raw)
            write_new(output / 'proposal.json', proposal.model_dump(mode='json'))
            if proposal.action == 'clarify':
                result.update(status='needs_clarification', stop_reason='caller_input_required', clarification=proposal.clarification)
            else:
                plan = TaskPlan(plan_id='query-plan-' + digest(request.model_dump(mode='json'))[:20], origin=plan_origin,
                    question=request.question, scope=request.scope, tasks=proposal.tasks)
                write_new(output / 'plan.json', plan.model_dump(mode='json'))
                logger.info('计划已生成：%s 个任务，%s 个取证要求', len(plan.tasks),
                            sum(len(t.requirements) for t in plan.tasks))
                if agent.max_steps <= 1:
                    result.update(status='limited', stop_reason='decision_limit')
                else:
                    executor = DataQueryAgent(agent.port, agent.planner, max_steps=agent.max_steps - 1,
                                              max_packet_bytes=agent.max_packet_bytes, turn_timeout=agent.turn_timeout)
                    execution = await executor.run_tasks(plan, output=output / 'execution')
                    result.update(status=execution['status'], stop_reason=execution['stop_reason'], execution=execution)
        except ValidationError as error:
            result.update(status='invalid_plan', stop_reason='proposal_contract_or_scope_invalid',
                          errors=error.errors(include_url=False, include_input=False, include_context=False))
        except Exception as error:
            result.update(status='failed', stop_reason=type(error).__name__)
    write_new(output / 'result.json', result)
    from uteki.agents.data_query.report import write_question_report
    write_question_report(output, output / 'report.md')
    write_new(output / 'manifest.json', {'files': {str(p.relative_to(output)): digest(p.read_bytes())
        for p in sorted(output.rglob('*')) if p.is_file()}})
    return result


def compact_progress(state):
    return [{'task_id': task['task_id'], 'requirements': [
        {**{k: req[k] for k in ('requirement_id', 'kind', 'availability', 'first_unread', 'last_read_cursor', 'record_ids', 'computed_ids')},
         'required_count': len(req['required_body']), 'returned_count': len(req['returned_body']),
         'unread_count': len(req['unread_body'])} for req in task['requirements']]} for task in state['tasks']]


def compact_completion(value):
    result = deepcopy(value)
    for task in result['tasks']:
        for req in task['requirements']:
            req.pop('retained_issues')  # Full history remains in the immutable session.
            for check in req['checks']:
                for key in ('artifact_ids', 'record_ids', 'computed_ids', 'event_sequences'):
                    check.pop(key)
    return result


def evidence_fingerprint(state):
    return digest([[{k: req[k] for k in ('returned_body', 'image_references', 'artifact_ids', 'record_ids', 'computed_ids')}
                    for req in task['requirements']] for task in state['tasks']])


async def run_task_loop(agent, plan, *, output):
    plan = TaskPlan.model_validate(plan)
    output = Path(output).resolve()
    if output.is_relative_to(agent.port.dataset):
        raise ValueError('Task loop output must be outside the frozen dataset')
    # Validate scope before creating output, preserving the existing shared boundaries.
    agent.port.scoped(plan.scope)
    output.mkdir(parents=True, exist_ok=False)
    session = TaskProgressSession(agent.port, plan, output=output / 'session',
                                  max_steps=agent.max_steps, completion_checks=True)
    write_new(output / 'loop-config.json', {'decision_limit': agent.max_steps, 'tool_limit': agent.max_steps,
        'max_packet_bytes': agent.max_packet_bytes, 'turn_timeout': agent.turn_timeout, 'no_progress_limit': 3,
        'plan_origin': plan.origin, 'plan_revisions': 'unsupported'})
    history, observation, turns = [], None, []
    stagnant = 0
    stop, reason = 'limited', 'decision_limit'
    for number in range(1, agent.max_steps + 1):
        completion = session.check_completion()
        packet = {'plan': plan.model_dump(mode='json'), 'progress': compact_progress(session.snapshot),
                  'completion': compact_completion(completion), 'observation': observation,
                  'history': history, 'decisions_remaining': agent.max_steps - number + 1}
        if len(json.dumps(packet, ensure_ascii=False).encode()) > agent.max_packet_bytes:
            reason = 'context_budget_exceeded'
            break
        folder = output / f'turn-{number:02d}'
        write_new(folder / 'input.json', packet)
        logger.info('第 %s 轮：等待模型选择动作', number)
        before = evidence_fingerprint(session.snapshot)
        action = None
        terminate = False
        try:
            raw = await asyncio.wait_for(agent.planner.decide(deepcopy(packet)), timeout=agent.turn_timeout)
            action = TaskPlannerDecision.model_validate(raw)
            write_new(folder / 'decision.json', action.model_dump(mode='json'))
            if action.action == 'finish':
                if completion['finish_allowed']:
                    stop, reason, terminate = 'retrieval_satisfied', 'host_conditions_satisfied', True
                    observation = {'status': 'finish_accepted'}
                else:
                    observation = {'status': 'finish_rejected', 'reason': 'host_conditions_unsatisfied',
                                   'detail': 'Use the current completion checks to retrieve missing evidence.'}
            elif action.action == 'clarify':
                stop, reason, terminate = 'needs_clarification', 'caller_input_required', True
                observation = {'status': 'needs_clarification', 'question': action.clarification}
            else:
                executed = session.execute(action.step)
                observation = {'status': executed['event']['outcome'], 'event_sequence': executed['event']['sequence'],
                               'error': executed['event']['error'], 'result': executed['result']}
        except ValidationError as error:
            observation = {'status': 'invalid_decision', 'reason': 'decision_contract_invalid',
                           'errors': error.errors(include_url=False, include_input=False, include_context=False)}
        except Exception as error:
            # Provider exceptions may contain private inputs/headers; retain type only.
            stop, reason, terminate = 'failed', type(error).__name__, True
            observation = {'status': 'failed', 'reason': reason}
        stagnant = stagnant + 1 if before == evidence_fingerprint(session.snapshot) else 0
        completion = session.check_completion()
        row = {'turn': number, 'action': action.action if action else 'invalid',
               'step': action.step.model_dump(mode='json') if action and action.step else None,
               'feedback': observation['status'], 'event_sequence': observation.get('event_sequence'),
               'consecutive_no_progress': stagnant, 'completion_status': completion['status'],
               'progress': compact_progress(session.snapshot)}
        write_new(folder / 'feedback.json', observation)
        write_new(folder / 'summary.json', row)
        turns.append(row)
        coverage = ', '.join(f"{r['returned_count']}/{r['required_count']}"
            for t in row['progress'] for r in t['requirements'] if r['kind'] == 'read_node')
        logger.info('第 %s 轮：%s → %s；取证 %s%s', number,
            action.step.action if action and action.step else row['action'], row['feedback'],
            row['completion_status'], '; 正文 ' + coverage if coverage else '')
        history.append({k: row[k] for k in ('turn', 'action', 'feedback', 'event_sequence', 'consecutive_no_progress')})
        if terminate:
            break
        if stagnant >= 3:
            stop, reason = 'limited', 'no_progress_limit'
            break
    stored = session.close()
    # If the last allowed decision obtained the remaining evidence, no extra
    # model round is needed just to acknowledge the host's satisfied conditions.
    if stop == 'limited' and stored['completion']['finish_allowed']:
        stop, reason = 'retrieval_satisfied', 'host_conditions_satisfied'
    result = {'status': stop, 'stop_reason': reason, 'plan_id': plan.plan_id, 'plan_origin': plan.origin,
              'planner_attempts': len(turns), 'tool_steps': stored['recorded_steps'], 'turns': turns,
              'decision_limit': agent.max_steps, 'decisions_remaining': agent.max_steps - len(turns),
              'completion': stored['completion'], 'progress': compact_progress(stored['state']),
              'session_result': 'session/result.json', 'last_feedback': observation,
              'semantic_completeness': 'not_evaluated'}
    write_new(output / 'result.json', result)
    write_new(output / 'manifest.json', {'files': {str(p.relative_to(output)): digest(p.read_bytes())
        for p in sorted(output.rglob('*')) if p.is_file()}})
    return result
