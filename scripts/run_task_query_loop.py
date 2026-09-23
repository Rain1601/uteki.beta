"""Offline feedback-driven fixture: validate the loop without paid model calls."""
import argparse
import asyncio
import json
from pathlib import Path

from scripts.run_task_progress import table, describe_completion
from uteki.agents.data_query.agent import DataQueryAgent
from uteki.agents.data_query.artifacts import write_new
from uteki.domain.research_data.task_plan import TaskPlan
from uteki.infrastructure.research_data.financial_records import digest
from uteki.infrastructure.research_data.query_service import QueryDataPort

ROOT = Path(__file__).resolve().parents[1]


class FeedbackFixturePlanner:
    """Test driver choosing from observed gaps; no predetermined block list/model."""
    def __init__(self, *, read_count=12, probe_early_finish=True, verbose=False):
        self.read_count, self.probe = read_count, probe_early_finish
        self.verbose = verbose

    async def decide(self, packet):
        if self.verbose:
            print('观察进度：' + ', '.join(f"{t['task_id']} {r['returned_count']}/{r['required_count']}"
                for t in packet['progress'] for r in t['requirements'] if r['kind'] == 'read_node'), flush=True)
        if self.probe:
            self.probe = False
            return {'action': 'finish'}
        if packet['completion']['finish_allowed']:
            return {'action': 'finish'}
        tracked = {t['task_id']: t for t in packet['progress']}
        assessed = {t['task_id']: t for t in packet['completion']['tasks']}
        for task in packet['plan']['tasks']:
            assessment = assessed[task['task_id']]
            if any(d['status'] != 'satisfied' for d in assessment['dependency_checks']):
                continue
            for req, status, progress in zip(task['requirements'], assessment['requirements'], tracked[task['task_id']]['requirements']):
                if status['status'] == 'satisfied':
                    continue
                base = {'task_id': task['task_id'], 'requirement_id': req['requirement_id']}
                if req['kind'] == 'read_node' and progress['first_unread']:
                    return {'action': 'execute', 'step': {**base, 'action': 'read_source', 'read': {
                        'source_snapshot_id': req['source_snapshot_id'], 'node_id': req['node_id'],
                        'start_block_id': progress['first_unread']['block_id'], 'count': self.read_count}}}
                if req['kind'] == 'query':
                    return {'action': 'execute', 'step': {**base, 'action': 'query', 'query': req['query']}}
        return {'action': 'clarify', 'clarification': '当前范围内没有可推进的任务，请检查缺口。'}


async def run_fixture(spec_path, output, *, verbose=False):
    spec = json.loads(Path(spec_path).read_text())
    if spec['schema_version'] != 'task-react-fixture-v1':
        raise ValueError('Expected an explicit offline task loop fixture')
    plan = TaskPlan.model_validate(spec['plan'])
    if plan.origin != 'scripted_fixture':
        raise ValueError('This runner only accepts scripted_fixture plans')
    dataset = ROOT / spec['dataset']
    before = {str(p.relative_to(dataset)): digest(p.read_bytes()) for p in dataset.rglob('*') if p.is_file()}
    planner = FeedbackFixturePlanner(read_count=spec['read_count'], probe_early_finish=spec['probe_early_finish'], verbose=verbose)
    with QueryDataPort(dataset) as port:
        result = await DataQueryAgent(port, planner, max_steps=spec['max_steps']).run_tasks(plan, output=output)
    after = {str(p.relative_to(dataset)): digest(p.read_bytes()) for p in dataset.rglob('*') if p.is_file()}
    if before != after:
        raise ValueError('Frozen dataset changed')
    rows = []
    for turn in result['turns']:
        body = ', '.join(f"{t['task_id']}: {r['returned_count']}/{r['required_count']}"
            for t in turn['progress'] for r in t['requirements'] if r['kind'] == 'read_node')
        step = turn['step']
        action = step['action'] + ' · ' + step['task_id'] if step else turn['action']
        rows.append([turn['turn'], action, turn['feedback'], body, turn['completion_status']])
    report = ['# 根据缺口继续执行：本轮结果', '', plan.question, '',
        '这是读取真实冻结资料的离线测试，决策由明确的规则模拟规划器生成，模型调用为 0；不证明模型自主决策质量。', '',
        '输入：登记计划、指定来源和已有数据库。每轮读取实际进度与缺口后选择下一步；不预设正文块列表。', '',
        f"结果：{result['status']}；规划器尝试 {result['planner_attempts']} 次；实际工具执行 {result['tool_steps']} 次。", '',
        table(['轮', '动作', '反馈', '正文进度', '取证条件'], rows), '',
        *describe_completion(result['completion']),
        '每轮输入/决策/反馈在 turn-XX/；原文、数字、证据包和逐步判定在 session/event-XXXX/。', '',
        '全文业务分析、风险分析与模型真实调用未验收。计划由调用方提供，自动拆题和计划修订尚未实现。', '']
    output = Path(output)
    (output / 'README.md').write_text('\n'.join(report))
    write_new(output / 'fixture.json', spec)
    write_new(output / 'verification.json', {'model_calls': 0, 'dataset_unchanged': True,
        'status': result['status'], 'planner_attempts': result['planner_attempts'], 'tool_steps': result['tool_steps'],
        'loop_manifest_sha256': digest((output / 'manifest.json').read_bytes())})
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = asyncio.run(run_fixture(args.spec, args.output, verbose=True))
    print(result['status'], result['stop_reason'])
