"""Execute a registered offline task fixture and verify identical tool/state replay."""
import argparse
import html
import json
from pathlib import Path
import tempfile

from uteki.agents.data_query.artifacts import write_new
from uteki.domain.research_data.task_plan import TaskPlan, TaskStep
from uteki.domain.research_data.task_completion import COMPLETION_VERSION
from uteki.infrastructure.research_data.financial_records import digest
from uteki.infrastructure.research_data.query_service import QueryDataPort
from uteki.infrastructure.research_data.task_progress import TaskProgressSession, replay_task_session

ROOT = Path(__file__).resolve().parents[1]


def cell(value):
    text = html.escape(str(value), quote=False)
    for char in ('\\', '|', '`', '*', '_', '[', ']'):
        text = text.replace(char, '\\' + char)
    return text.replace('\n', '<br>')


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join('---' for _ in headers) + ' |',
                     *['| ' + ' | '.join(cell(v) for v in row) + ' |' for row in rows]])


def period_text(period):
    return period['start'] + ' — ' + period['end']


CONDITIONS = {
    'all_body_blocks_returned': '指定章节的正文块全部返回',
    'requested_records_and_calculations_returned': '所需记录和计算结果返回',
    'caller_clarification_required': '调用方澄清缺失条件',
}
ACTIONS = {'outline_source': '查看目录', 'read_source': '读取正文',
           'search_source': '字面搜索', 'query': '查询与计算'}
STATUSES = {'satisfied': '取证条件满足', 'missing_evidence': '仍缺证据', 'blocked': '受阻', 'limited': '达到步数上限'}


def describe_completion(assessment, task_id=None):
    rows = []
    for task in assessment['tasks']:
        if task_id is not None and task['task_id'] != task_id:
            continue
        for condition in task['dependency_checks']:
            rows.append([task['task_id'], '前置依赖', STATUSES[condition['status']], condition['detail']])
        for req in task['requirements']:
            for condition in req['checks']:
                rows.append([task['task_id'], req['requirement_id'], STATUSES[condition['status']], condition['detail']])
    return [table(['任务', '要求', '程序检查', '判定依据 / 缺口'], rows), '',
            '本轮整体：' + STATUSES[assessment['status']] + '；剩余执行步数：' + str(assessment['steps_remaining'])
            + '；允许声明取证条件已满足：' + ('是' if assessment['finish_allowed'] else '否') + '。语义充分性未评估。', '']


def describe_request(request):
    action = request['action']
    if action == 'query':
        query = request['query']
        rows = [[r['entity_id'], r['metric_id'], period_text(r['period']), '原始记录']
                for r in query['records']]
        rows += [[r['entity_id'], r['formula_id'], ', '.join(period_text(p) for p in r['periods']), '计算']
                 for r in query['calculations']]
        return [table(['实体', '指标 / 公式', '明确期间', '请求类型'], rows), '']
    payload = request[{'outline_source': 'outline', 'read_source': 'read', 'search_source': 'search'}[action]]
    rows = [['动作', ACTIONS[action]], ['来源', payload['source_snapshot_id']]]
    if action != 'outline_source':
        rows.append(['章节', payload['node_id']])
    if action == 'read_source':
        start = (payload.get('cursor') or {}).get('start_block_id') or payload.get('start_block_id')
        rows += [['起点', start or '选定章节起始块'], ['请求块数', payload['count']]]
    elif action == 'search_source':
        rows += [['字面词', payload['phrase']], ['最多返回', payload['limit']]]
    return [table(['输入', '值'], rows), '']


def render_report(plan, results):
    tasks = {task['task_id']: task for task in plan['tasks']}
    checked = bool(results and 'completion' in results[-1])
    lines = ['# 任务计划与实际取证：逐步验收', '',
             ('本轮使用预设计划，0 次模型调用。程序检查明确的取证条件，语义充分性未评估；没有生成完整业务/风险分析。' if checked else
              '本轮使用预设计划，0 次模型调用。任务完成判定和语义完整性均未评估；没有生成完整业务/风险分析。'), '',
             '## 输入与条件', '', cell(plan['question']), '',
             '- 明确来源：' + cell(', '.join(plan['scope']['source_snapshot_ids'])),
             '- 信息截止日：' + cell(plan['scope']['knowledge_cutoff']),
             '- 候选数据：' + ('显式允许；未采纳' if plan['scope']['include_candidates'] else '不允许'),
             '- 任务计划、原文、已有数据库值与本轮取证进度分别保存。', '',
             table(['任务', '要取得什么', '取证条件（程序检查）' if checked else '完成条件（只登记，尚未执行完成判定）'], [
                 [task['task_id'], task['requested_information'], ', '.join(CONDITIONS[r['condition']] for r in task['requirements'])]
                 for task in plan['tasks']]), '', '## 每一步实际发生了什么', '']
    rows = []
    for item in results:
        event, state, value = item['event'], item['state'], item['result'] or {}
        task = next((t for t in state['tasks'] if t['task_id'] == event['task_id']), None)
        req = next((r for r in task['requirements'] if r['requirement_id'] == event['requirement_id']), None) if task else None
        returned = f"{len(value.get('blocks', []))} 块 / {len(value.get('records', []))} 行 / {len(value.get('computed_facts', []))} 计算"
        if event['action'] in ('outline_source', 'search_source'):
            returned = f"目录 {len(value.get('nodes', []))} 项 / 搜索命中 {value.get('total', 0)}；不计正文"
        progress = f"正文去重 {len(req['returned_body'])} / 范围内 {len(req['required_body'])}；未读 {len(req['unread_body'])}" if req and req['kind'] == 'read_node' and req['availability'] == 'available' else ('查询状态：' + str(req['observed_query_status']) if req and req['kind'] == 'query' else '范围不可用或需澄清')
        rows.append([event['sequence'], event['task_id'], ACTIONS[event['action']],
                     '已记录' if event['outcome'] == 'recorded' else '失败；返回不计入进度', returned, progress])
    lines += [table(['步', '任务', '动作', '记录状态', '实际返回', '当前进度'], rows), '',
              '“范围内”由明确选定的章节和冻结索引决定；包含标题，排除图片、页码及已标记的页眉页脚。块数表示读取量，不代表结论数量。', '']
    for item in results:
        event, value, package = item['event'], item['result'] or {}, item['package'] or {}
        lines += [f"## Step {event['sequence']} · {cell(tasks.get(event['task_id'], {}).get('requested_information', event['task_id']))}", '',
                  '输入任务 / 要求：' + cell(event['task_id'] + ' / ' + event['requirement_id']), '',
                  '完整请求与工具返回：`session/event-' + f"{event['sequence']:04d}" + '/`。', '']
        lines += describe_request(item['request'])
        if event['error']:
            lines += ['执行错误：' + cell(event['error']['detail']), '']
        if value.get('nodes'):
            lines += [table(['目录 ID', '标题'], [[node['node_id'], node.get('title', '')]
                      for node in value['nodes']]), '']
        if value.get('hits'):
            lines += [table(['命中块', '预览（不计正文进度）'], [[hit['block_id'], hit.get('preview', '')]
                      for hit in value['hits']]), '']
        for block in value.get('blocks', []):
            lines += ['- ' + cell(block['block_id'] + ' · ' + block['type'])]
            if block['type'] == 'image':
                lines += ['  - 仅图片引用，替代文字：' + cell(block['text'])]
            else:
                lines += ['', '> ' + cell(block['text']), '']
        records = value.get('records', [])
        if records:
            lines += [table(['实体', '指标', '期间', '值', '单位', '记录 ID'], [[r['entity_id'], r['metric_id'],
                period_text(r['period']), r['value_decimal'], r['unit'], r['record_id']] for r in records]), '']
        for fact in value.get('computed_facts', []):
            lines += ['- 计算：' + cell(fact['formula_id']) + ' = ' + cell(fact['display_decimal']) + ' ' + cell(fact['unit']),
                      '  - 输入记录：' + cell(', '.join(fact['operand_record_ids'])), '']
        lines += ['- 本步证据包：' + cell(package.get('bundle_id', '未生成')),
                  '- 本步证据缺口：' + cell(len(package.get('gaps', []))), '']
        if checked:
            lines += describe_completion(item['completion'], event['task_id'])
    lines += ['## 最后仍缺什么', '']
    final = results[-1]['state'] if results else None
    if final:
        for task in final['tasks']:
            for req in task['requirements']:
                lines += ['- ' + cell(task['task_id'] + ' / ' + req['requirement_id']) + '：']
                if req['kind'] == 'read_node':
                    lines += ['  - 未读块数：' + cell(len(req['unread_body'])) + '；范围状态：' + cell(req['availability']),
                              '  - 最早未读位置：' + cell(req['first_unread']['block_id'] if req['first_unread'] else '无未读正文或范围不可用，请结合范围状态判断'),
                              '  - 最近一次工具的续读位置：' + cell(req['last_read_cursor']['start_block_id'] if req['last_read_cursor'] else '无；不能据此认为前文已读完')]
                lines += ['  - 累积问题记录：' + cell(len(req['issues'])) + ('；工程判定见下表，历史问题不会被删除。' if checked else '；完成判定：未评估。')]
    if checked:
        lines += ['', *describe_completion(results[-1]['completion']),
                  '检查详情中的 artifact_ids、record_ids、computed_ids 和 event_sequences 可追溯到对应证据；每步保存于 completion.json。', '',
                  '满足取证条件仅表示明确计划的工程要求达到；抽取是否遗漏、计划是否完整、分析是否充分仍未评估。', '']
    else:
        lines += ['', '该样例验证取证归属、去重、未读范围和可复放性。计划是否拆全问题、证据是否足以支持业务/风险判断、任务何时完成仍留待后续验收。', '']
    return '\n'.join(lines)


def run_fixture(root, spec_path, output):
    spec = json.loads(Path(spec_path).read_text())
    if spec['schema_version'] not in ('task-progress-replay-v1', 'task-completion-replay-v1'):
        raise ValueError('Unsupported task replay specification')
    checked = spec['schema_version'] == 'task-completion-replay-v1'
    plan = TaskPlan.model_validate(spec['plan'])
    if plan.origin != 'scripted_fixture':
        raise ValueError('Offline fixture runner requires explicit scripted_fixture origin')
    dataset = (Path(root) / spec['dataset']).resolve()
    output = Path(output).resolve()
    if output.is_relative_to(dataset):
        raise ValueError('Output cannot be inside dataset')
    before = {str(p.relative_to(dataset)): digest(p.read_bytes()) for p in dataset.rglob('*') if p.is_file()}
    output.mkdir(parents=True, exist_ok=False)
    write_new(output / 'spec.json', spec)
    results = []
    with QueryDataPort(dataset) as port:
        session = TaskProgressSession(port, plan, output=output / 'session', max_steps=spec['max_steps'], completion_checks=checked)
        for operation in spec['steps']:
            if set(operation) == {'step'}:
                action = operation['step']
            elif set(operation) == {'continue_read'}:
                continuation = operation['continue_read']
                index = continuation['from_event'] - 1
                if not 0 <= index < len(results):
                    raise ValueError('Continuation references an unavailable event')
                prior = results[index]
                cursor = (prior['result'] or {}).get('next_cursor')
                if prior['event']['outcome'] != 'recorded' or prior['event']['action'] != 'read_source' or not cursor:
                    raise ValueError('Continuation requires a successful explicit read event with a cursor')
                action = {'task_id': prior['event']['task_id'], 'requirement_id': prior['event']['requirement_id'],
                          'action': 'read_source', 'read': {'source_snapshot_id': cursor['source_snapshot_id'],
                          'node_id': cursor['node_id'], 'cursor': cursor, 'count': continuation['count']}}
            else:
                raise ValueError('Each replay operation requires exactly one step or continuation')
            step = TaskStep.model_validate(action)
            results.append({'request': step.model_dump(mode='json'), **session.execute(step)})
        result = session.close()
        manifest_hash = digest((output / 'session/manifest.json').read_bytes())
        with tempfile.TemporaryDirectory(prefix='uteki-task-replay-') as temp:
            replayed = replay_task_session(port, output / 'session', output=Path(temp) / 'session',
                                           expected_manifest_sha256=manifest_hash)
        if replayed != result:
            raise ValueError('Task replay diverged')
    after = {str(p.relative_to(dataset)): digest(p.read_bytes()) for p in dataset.rglob('*') if p.is_file()}
    if before != after:
        raise ValueError('Frozen dataset changed')
    (output / 'README.md').write_text(render_report(plan.model_dump(mode='json'), results))
    verification = {'schema_version': 'task-progress-verification-v1',
        'model_calls': 0, 'dataset_unchanged': True, 'identical_tool_and_progress_replay': True,
        'session_manifest_sha256': manifest_hash, 'recorded_steps': len(results),
        'execution_errors': sum(r['event']['outcome'] == 'error' for r in results),
        'files': {str(p.relative_to(output)): digest(p.read_bytes()) for p in output.rglob('*') if p.is_file()}}
    if checked:
        verification.update(completion_rules_version=COMPLETION_VERSION, identical_completion_replay=True,
                            completion_status=result['completion']['status'], finish_allowed=result['completion']['finish_allowed'])
    write_new(output / 'verification.json', verification)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run_fixture(ROOT, args.spec, args.output)
    print(json.dumps({'recorded_steps': result['recorded_steps'], 'model_calls': 0,
                      'task_completion': result['task_completion']}, ensure_ascii=False))
