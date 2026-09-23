"""Persist offline Data Agent acceptance examples using real tools and scripted decisions."""
import argparse
import asyncio
import copy
import json
from pathlib import Path

from scripts.run_task_query_loop import FeedbackFixturePlanner, run_fixture
from uteki.agents.data_query.agent import DataQueryAgent
from uteki.agents.data_query.artifacts import write_new
from uteki.infrastructure.research_data.financial_records import digest
from uteki.infrastructure.research_data.query_service import QueryDataPort
from tests.unit.test_scoped_query_service import make_scoped_dataset, year
from tests.unit.test_task_completion import attach_synthetic_quotes
from tests.unit.test_task_progress import plan

ROOT = Path(__file__).resolve().parents[1]


class ScriptedProposal(FeedbackFixturePlanner):
    """Fixture tasks are test input, not model-generated plans or reference answers."""
    plan_origin = "scripted_fixture"

    def __init__(self, tasks):
        super().__init__(read_count=2, probe_early_finish=False)
        self.tasks = tasks

    async def draft_plan(self, packet):
        return {'action': 'plan', 'tasks': self.tasks}


def hashes(folder):
    return {str(p.relative_to(folder)): digest(p.read_bytes()) for p in folder.rglob('*') if p.is_file()}


async def run(output):
    output.mkdir(parents=True, exist_ok=False)
    dataset = output / 'synthetic-dataset'
    dataset.mkdir()
    make_scoped_dataset(dataset)
    attach_synthetic_quotes(dataset)
    before = hashes(dataset)
    rows = []
    real = await run_fixture(ROOT / 'experiments/data_agent_query/task-react-v1/spec.json', output / 'alphabet-mixed')
    assert real['status'] == 'retrieval_satisfied'
    body = real['progress'][0]['requirements'][0]
    assert (body['returned_count'], body['required_count'], body['unread_count']) == (79, 79, 0)
    rows.append({'case': 'alphabet-mixed', 'status': real['status'], 'body': '79/79', 'tool_steps': real['tool_steps']})
    with QueryDataPort(dataset) as port:
        cases = [('acme-mixed', plan())]
        other = plan()
        other['scope'].update(company_ids=['other'], source_snapshot_ids=['other-annual'])
        other['question'] = 'Read Business and retrieve Other Services revenue for FY2031.'
        for task in other['tasks']:
            task['source_snapshot_ids'] = ['other-annual']
        other['tasks'][0]['requirements'][0]['source_snapshot_id'] = 'other-annual'
        other['tasks'][1]['requirements'][0]['query'] = {'records': [{'entity_id': 'other-services', 'metric_id': 'revenue', 'period': year(2031)}]}
        cases.append(('other-company', other))
        missing = copy.deepcopy(other)
        missing['question'] = 'Read Business and calculate Other Services margin for FY2031.'
        missing['tasks'][1]['requirements'][0]['query'] = {'calculations': [{'formula_id': 'operating_margin', 'entity_id': 'other-services', 'periods': [year(2031)]}]}
        cases.append(('missing-income', missing))
        prior = plan()
        prior['question'] = 'Retrieve Acme Services revenue for FY2030.'
        prior['tasks'] = prior['tasks'][1:]
        prior['tasks'][0]['requirements'][0]['query'] = {'records': [{'entity_id': 'acme-services', 'metric_id': 'revenue', 'period': year(2030)}]}
        cases.append(('prior-period', prior))
        for name, configured in cases:
            request = {key: configured[key] for key in ('question', 'scope')}
            result = await DataQueryAgent(port, ScriptedProposal(configured['tasks']), max_steps=8).run_question(request, output=output / name)
            execution = result['execution']
            if name == 'missing-income':
                assert result['status'] == 'limited' and not execution['completion']['finish_allowed']
                assert execution['stop_reason'] == 'no_progress_limit'
            else:
                assert result['status'] == 'retrieval_satisfied'
            events = list((output / name / 'execution/session').glob('event-*/tool-result.json'))
            tool_results = [json.loads(p.read_text()) for p in events]
            records = [record for item in tool_results for record in item.get('records', [])]
            allowed = set(configured['scope']['source_snapshot_ids'])
            assert records and {r['source_snapshot_id'] for r in records} <= allowed
            if name == 'other-company':
                assert {r['value_decimal'] for r in records} == {'800'}
            if name == 'prior-period':
                assert {r['value_decimal'] for r in records} == {'90'}
            if name == 'acme-mixed':
                facts = [fact for item in tool_results for fact in item.get('computed_facts', [])]
                assert facts[0]['display_decimal'] == '15.00'
            rows.append({'case': name, 'status': result['status'], 'stop_reason': execution['stop_reason'],
                         'tool_steps': execution['tool_steps'], 'source_snapshot_ids': sorted(allowed)})
        for name, changes in [('missing-scope', {'company_ids': []}), ('cross-company-source', {'source_snapshot_ids': ['other-annual']})]:
            invalid = {**plan()['scope'], **changes}
            try:
                port.scoped(invalid)
            except ValueError as error:
                write_new(output / f'{name}.json', {'status': 'rejected', 'error': str(error), 'scope': invalid})
            else:
                raise AssertionError(f'{name} was not rejected')
            rows.append({'case': name, 'status': 'rejected'})
    assert before == hashes(dataset)
    write_new(output / 'verification.json', {'model_calls': 0, 'decision_source': 'scripted_fixture',
        'dataset_unchanged': True, 'synthetic_dataset_hashes': before, 'cases': rows})
    lines = ['# Data Agent 离线端到端验收', '',
        '模型调用 0 次。使用显式脚本规划器、真实 QueryDataPort、DuckDB、正文读取、完成条件、证据包和报告；不能证明模型拆题或 Analysis Agent 推理质量。', '',
        '| 用例 | 结果 |', '| --- | --- |']
    lines += [f"| {r['case']} | {r['status']} |" for r in rows]
    lines += ['', 'Alphabet 混合用例：完整 Business 79/79 块和营业利润率查询。独立合成公司 Acme：3/3 块和 15.00%；Other：3/3 块和收入 800 USD；上一年度收入 90 USD。合成值由测试数据明确声明，不代表真实公司或抽取泛化。', '',
        '缺资料用例：Other 没有营业利润；实际查询保留缺口、未获完成许可。脚本规划器重复查询后触发 no_progress_limit，尚未证明模型能够主动澄清；该限制在各轮 feedback 与 completion 中保留。', '',
        '每例 report.md、原文报告及 execution/session/event-* 保存可核查产物；Alphabet 例沿用既有显式任务计划。合成 run_question 例使用脚本 draft_plan，计划 origin=scripted_fixture，与本文件和 verification.json 一致。', '',
        '下一步：使用同一费用账本运行真实模型混合问题及缺资料问题；再增加另一家真实公司已审核数据源。', '']
    (output / 'README.md').write_text('\n'.join(lines))
    return rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.output)), ensure_ascii=False, indent=2))
