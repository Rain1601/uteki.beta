"""Evaluate host-owned progress against verified receipts; never query a model.

Constructed by TaskProgressSession with its frozen node inventories. Receipts
must have passed that session's canonical evidence packager. External callers
use the session (or hash-pinned replay), never submit self-declared completion.
"""
from copy import deepcopy

from uteki.domain.research_data.task_completion import CompletionAssessment, aggregate
from uteki.domain.research_data.task_plan import TaskPlan, ProgressSnapshot
from .financial_records import digest
from .query_service import QueryDataPort


def check(key, status, reason, detail, **refs):
    return dict(check_id=key, status=status, reason=reason, detail=detail, **refs)


class TaskCompletionEvaluator:
    def __init__(self, plan, inventories):
        self._plan = TaskPlan.model_validate(plan).model_copy(deep=True)
        self._inventories = deepcopy(inventories)

    def evaluate(self, progress, receipts, *, step_limit):
        state = ProgressSnapshot.model_validate(progress).model_dump(mode='json')
        plan = self._plan
        if (state['plan_id'] != plan.plan_id or state['plan_sha256'] != digest(plan.model_dump(mode='json'))
                or state['snapshot_id'] != plan.scope.snapshot_id):
            raise ValueError('Completion input differs from the bound plan/snapshot')
        if [t['task_id'] for t in state['tasks']] != [t.task_id for t in plan.tasks]:
            raise ValueError('Completion input cannot omit, reorder or introduce tasks')
        if not 0 <= state['sequence'] <= step_limit:
            raise ValueError('Completion progress exceeds the original execution limit')
        known = {(t.task_id, r.requirement_id) for t in plan.tasks for r in t.requirements}
        if any((r['request']['task_id'], r['request']['requirement_id']) not in known
               or not 0 < r['sequence'] <= state['sequence'] for r in receipts):
            raise ValueError('Completion receipt is not bound to this task history')
        if len({r['sequence'] for r in receipts}) != len(receipts):
            raise ValueError('Duplicate completion receipts')
        local = {}
        for task, tracked in zip(plan.tasks, state['tasks']):
            if [r['requirement_id'] for r in tracked['requirements']] != [r.requirement_id for r in task.requirements]:
                raise ValueError('Completion input cannot omit or introduce requirements')
            requirements = []
            for req, observed in zip(task.requirements, tracked['requirements']):
                if req.kind != observed['kind']:
                    raise ValueError('Completion requirement kind changed')
                own = [r for r in receipts if r['request']['task_id'] == task.task_id
                       and r['request']['requirement_id'] == req.requirement_id]
                if req.kind == 'read_node':
                    checks = self._read(task, req, observed, own)
                elif req.kind == 'query':
                    checks = self._query(req, own)
                else:
                    checks = [check('clarification', 'blocked', 'caller_clarification_required', req.question)]
                requirements.append(dict(requirement_id=req.requirement_id, condition=req.condition,
                    status=aggregate(c['status'] for c in checks), checks=checks, retained_issues=observed['issues']))
            local[task.task_id] = dict(task_id=task.task_id, requirements=requirements)
        evaluated = {}

        def visit(task):
            if task.task_id in evaluated:
                return evaluated[task.task_id]
            dependencies = []
            for parent_id in task.depends_on:
                parent = visit(next(t for t in plan.tasks if t.task_id == parent_id))
                ok = parent['status'] == 'satisfied'
                dependencies.append(check('dependency:' + parent_id, 'satisfied' if ok else 'blocked',
                    'dependency_satisfied' if ok else 'dependency_unsatisfied',
                    '前置任务 ' + parent_id + (' 的取证条件已满足。' if ok else ' 的取证条件尚未满足。')))
            row = local[task.task_id]
            row.update(dependency_checks=dependencies,
                       status=aggregate([r['status'] for r in row['requirements']] + [d['status'] for d in dependencies]))
            evaluated[task.task_id] = row
            return row

        tasks = [visit(t) for t in plan.tasks]
        status = aggregate(t['status'] for t in tasks)
        remaining = step_limit - state['sequence']
        return CompletionAssessment(plan_id=plan.plan_id, plan_sha256=state['plan_sha256'],
            progress_sha256=digest(state), sequence=state['sequence'], step_limit=step_limit,
            steps_remaining=remaining, conditions_status=status,
            status='limited' if not remaining and status != 'satisfied' else status,
            finish_allowed=status == 'satisfied', tasks=tasks).model_dump(mode='json')

    def _read(self, task, req, state, receipts):
        inventory = self._inventories[(task.task_id, req.requirement_id)]
        if state['availability'] != inventory['status'] or state['required_body'] != inventory['body']:
            raise ValueError('Completion reading inventory differs from frozen node')
        if inventory['status'] != 'available':
            return [check('read_scope', 'blocked', inventory['status'], '指定正文范围不可用，不能按零未读判定完成。')]
        if not inventory['body']:
            return [check('read_scope', 'blocked', 'no_body_blocks', '该范围没有可核验正文；图片或布局块不能替代正文要求。')]
        seen, aids, sequences = set(), set(), []
        for receipt in receipts:
            value = receipt['result']
            if receipt['request']['action'] != 'read_source' or value['status'] != 'read':
                continue
            if value['source_snapshot_id'] != req.source_snapshot_id or value['node_id'] != req.node_id:
                raise ValueError('Read receipt differs from requirement')
            sequences.append(receipt['sequence'])
            package = receipt['package']
            roots = [a for a in package['artifacts'] if a['kind'] in ('source_text', 'source_table')
                     and a['provenance']['verification'] == 'source_verified']
            for block in value['blocks']:
                entry = inventory['blocks'][block['block_id']]
                if entry['mode'] != 'body':
                    continue
                matches = [a for a in roots if a['payload']['block'] == block and any(
                    loc['source_snapshot_id'] == req.source_snapshot_id and loc['index_id'] == entry['ref']['index_id']
                    and loc['block_id'] == block['block_id'] for loc in a['locators'])]
                if not matches:
                    raise ValueError('Read receipt has no verified source artifact')
                seen.add(digest(entry['ref']))
                aids.update(a['artifact_id'] for a in matches)
        unread = [ref for ref in inventory['body'] if digest(ref) not in seen]
        if ({digest(ref) for ref in state['returned_body']} != seen or state['unread_body'] != unread
                or len(state['returned_body']) != len(seen)):
            raise ValueError('Reading progress differs from actual verified receipts')
        return [check('read_scope', 'satisfied', 'scope_available', '正文范围已绑定冻结来源和章节。'),
                check('body_coverage', 'missing_evidence' if unread else 'satisfied',
                      'unread_body_remaining' if unread else 'all_body_returned',
                      f"正文已返回 {len(seen)} / {len(inventory['body'])} 块；仍缺 {len(unread)} 块。",
                      artifact_ids=sorted(aids), event_sequences=sequences, remaining_count=len(unread))]

    def _query(self, req, receipts):
        queries = [r for r in receipts if r['request']['action'] == 'query']
        if not queries:
            return [check('query_execution', 'missing_evidence', 'query_not_returned', '尚无本要求的成功查询与已校验证据包。')]
        receipt = queries[-1]
        if receipt['request']['query'] != req.query.model_dump(mode='json'):
            raise ValueError('Query receipt differs from declared requirement')
        value, package = receipt['result'], receipt['package']
        artifacts = {a['artifact_id']: a for a in package['artifacts']}
        records = {r['record_id']: r for r in value['records']}
        calculations = list({digest(c.model_dump(mode='json')): c for c in req.query.calculations}.values())
        needs = {digest(r.model_dump(mode='json')): r.model_dump(mode='json') for r in req.query.records}
        for calc in calculations:
            needs.update({digest(r.model_dump(mode='json')): r.model_dump(mode='json') for r in QueryDataPort._dependencies(calc)})
        selections = {digest(s['request']): s for s in value['selections']}
        if len(selections) != len(value['selections']) or set(selections) != set(needs):
            raise ValueError('Query selections do not match the declared records/calculation dependencies')
        checks, cited = [], set()
        for key, need in needs.items():
            selection = selections[key]
            ids = selection['record_ids']
            matching = bool(ids) and all(rid in records and all(records[rid].get(k) == v for k, v in need.items()) for rid in ids)
            status = selection['status']
            ok = matching and status in ('matched', 'listed')
            blocked = status in ('unsupported', 'ambiguous', 'quality_filtered', 'not_available_at_cutoff')
            refs = [aid for rid in ids for aid in package['bindings'].get('record:' + rid, [])]
            if ok and any(not self._bound(package, artifacts, 'record:' + rid, 'normalized_record', 'record', records[rid]) for rid in ids):
                raise ValueError('Query record has no matching verified artifact')
            checks.append(check('records:' + key[:24], 'satisfied' if ok else 'blocked' if blocked else 'missing_evidence',
                'records_returned' if ok else 'record_mismatch' if status in ('matched', 'listed') else 'record_' + status,
                f"{need['entity_id']} / {need['metric_id']} / {need['period']['start']} — {need['period']['end']}："
                + ('取得匹配记录。' if ok else '尚未取得无冲突的匹配记录。'),
                record_ids=ids, artifact_ids=refs, event_sequences=[receipt['sequence']]))
            if not ok:
                continue
            for rid in ids:
                if rid in cited:
                    continue
                cited.add(rid)
                checks.append(self._citations(records[rid], package, artifacts, receipt['sequence']))
        for calc in calculations:
            payload = calc.model_dump(mode='json')
            facts = [f for f in value['computed_facts'] if f['formula_id'] == calc.formula_id + '-v1'
                     and f['entity_id'] == calc.entity_id and f['periods'] == payload['periods']]
            facts = list({digest(f): f for f in facts}.values())
            deps = [selections[digest(r.model_dump(mode='json'))] for r in QueryDataPort._dependencies(calc)]
            expected_ids = {rid for s in deps for rid in s['record_ids']}
            ok = len(facts) == 1 and all(s['status'] == 'matched' and s['record_ids'] for s in deps)
            ok = ok and set(facts[0]['operand_record_ids']) == expected_ids
            ok = ok and self._bound(package, artifacts, 'computed:' + facts[0]['computed_id'], 'computed_scalar', 'fact', facts[0])
            checks.append(check('calculation:' + digest(payload)[:24], 'satisfied' if ok else 'missing_evidence',
                'calculation_verified' if ok else 'calculation_or_operands_missing',
                calc.formula_id + (' 的输入完整，结果已由注册计算核验。' if ok else ' 缺少成功计算或完整、匹配的输入记录。'),
                record_ids=sorted(expected_ids), computed_ids=[f['computed_id'] for f in facts],
                artifact_ids=[aid for f in facts for aid in package['bindings'].get('computed:' + f['computed_id'], [])],
                event_sequences=[receipt['sequence']]))
        return checks

    @staticmethod
    def _bound(package, artifacts, key, kind, field, expected):
        ids = package['bindings'].get(key, [])
        return bool(ids) and all(aid in artifacts and artifacts[aid]['kind'] == kind
            and artifacts[aid]['payload'][field] == expected
            and artifacts[aid]['provenance']['verification'] in ('snapshot_verified', 'source_verified') for aid in ids)

    @staticmethod
    def _citations(record, package, artifacts, sequence):
        evidence_ids = set(record['evidence_ids'] + record['qualifier_evidence_ids'] + record['question_evidence_ids'])
        missing, refs = [], set()
        for eid in sorted(evidence_ids):
            ids = package['bindings'].get('evidence:' + eid, [])
            quotes = [artifacts[aid] for aid in ids]
            ok = bool(quotes) and all(a['kind'] == 'source_quote' and a['payload']['evidence']['evidence_id'] == eid
                and a['provenance']['verification'] == 'source_verified' and a['derived_from']
                and all(artifacts[p]['kind'] in ('source_text', 'source_table')
                        and artifacts[p]['provenance']['verification'] == 'source_verified' for p in a['derived_from'])
                and all(loc.get('source_sha256') and loc.get('source_url') and loc.get('available_at')
                        and loc.get('index_id') and loc.get('block_id') for loc in a['locators']) for a in quotes)
            refs.update(ids)
            if not ok:
                missing.append(eid)
        return check('citations:' + record['record_id'], 'missing_evidence' if missing else 'satisfied',
            'source_citation_missing' if missing else 'source_citations_verified',
            ('以下引用未能核验到原文：' + ', '.join(missing)) if missing else '记录及其条件、问答引用均已核验到原文。',
            record_ids=[record['record_id']], artifact_ids=sorted(refs), event_sequences=[sequence], remaining_count=len(missing))
