"""Readable retrieval receipts. No model calls, answer synthesis or new facts."""
import html
import json
from pathlib import Path
import re

from uteki.domain.research_data.evidence_package import EvidencePackage


def text(value):
    if value is None:
        return '未提供'
    value = html.escape(str(value), quote=False)
    return re.sub(r'([\\`*_\[\]|])', r'\\\1', value).replace('\n', '<br>')


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |',
                      '| ' + ' | '.join('---' for _ in headers) + ' |',
                      *['| ' + ' | '.join(text(v) for v in row) + ' |' for row in rows]])


def write_question_report(session, destination):
    """Render a saved question run into two new files; never rewrite run evidence."""
    session, destination = Path(session), Path(destination)
    result = json.loads((session / 'result.json').read_text())
    request = result['request']
    execution = result.get('execution', {})
    plan_file = session / 'plan.json'
    plan = json.loads(plan_file.read_text()) if plan_file.exists() else {'tasks': []}
    artifacts, sql_rows = {}, []
    for event in sorted((session / 'execution/session').glob('event-*')):
        bundle = event / 'evidence-package.json'
        if bundle.exists():
            package = EvidencePackage.model_validate_json(bundle.read_text())
            for artifact in package.artifacts:
                value = artifact.model_dump(mode='json')
                key = (package.scope.snapshot_id, artifact.artifact_id)
                if key in artifacts and artifacts[key] != value:
                    raise ValueError('Conflicting evidence artifact in report input')
                artifacts[key] = value
        tool_result = event / 'tool-result.json'
        if tool_result.exists():
            for item in json.loads(tool_result.read_text()).get('trace', []):
                if item.get('tool') == 'sql':
                    sql_rows.append(item)
    values = list(artifacts.values())
    records = [a['payload']['record'] for a in values if a['kind'] == 'normalized_record']
    facts = [a['payload']['fact'] for a in values if a['kind'] == 'computed_scalar']
    quotes = [a for a in values if a['kind'] == 'source_quote']
    blocks = {}
    for artifact in values:
        if artifact['kind'] not in ('source_text', 'source_table'):
            continue
        block = artifact['payload']['block']
        for sid in artifact['source_snapshot_ids']:
            blocks[(sid, block['block_id'])] = block
    text_file = destination.with_name(destination.stem + '-source-text.md')
    if destination.exists() or text_file.exists():
        raise FileExistsError('Reports must use new output paths')
    lines = ['# Data Agent 执行结果', '', text(request['question']), '',
        f"状态：**{text(result['status'])}**；停止原因：{text(result['stop_reason'])}。", '',
        f"计划请求 {result['planning_calls']} 次；执行决策 {execution.get('planner_attempts', 0)} 次；"
        f"工具执行 {execution.get('tool_steps', 0)} 次。", '',
        '这里展示实际取证结果；取证条件满足不代表业务/风险分析已经完成，候选数据也未被自动采纳。', '',
        '## 自动生成的任务', '',
        table(['任务', '信息要求', '取证方式'], [[t['task_id'], t['requested_information'],
            '、'.join(r['kind'] for r in t['requirements'])] for t in plan['tasks']]) if plan['tasks'] else '未生成有效任务计划。', '',
        '## 实际数字', '']
    if records:
        lines += [table(['实体', '指标', '期间', '数值', '单位', '口径'], [[r['entity_id'], r['metric_id'],
            f"{(r.get('period') or {}).get('start')} → {(r.get('period') or {}).get('end')}",
            r['value_decimal'], r['unit'], r['accounting_basis']] for r in records]), '']
    else:
        lines += ['本轮没有返回数值记录。', '']
    if facts:
        lines += [table(['实体', '公式', '结果', '单位', '输入记录'], [[f['entity_id'], f['formula_id'],
            f['display_decimal'], f['unit'], '、'.join(f['operand_record_ids'])] for f in facts]), '']
    if quotes:
        lines += ['## 原文引用', '', table(['原文', '来源', '页码 / 块'], [[a['payload']['text'],
            '、'.join(a['source_snapshot_ids']), '；'.join(f"{loc.get('reported_page')} / {loc.get('block_id')}"
            for loc in a['locators'])] for a in quotes]), '']
    lines += ['## 阅读覆盖与缺口', '']
    progress = [(t, r) for t in execution.get('progress', []) for r in t['requirements'] if r['kind'] == 'read_node']
    if progress:
        lines += [table(['要求', '已返回 / 要求总量', '未读', '下次起点'], [[r['requirement_id'],
            f"{r['returned_count']} / {r['required_count']}", r['unread_count'],
            (r.get('first_unread') or {}).get('block_id', '无')] for _, r in progress]), '']
    else:
        lines += ['本轮未设置章节全文阅读要求；数字出处不等于整章已读。', '']
    for task in execution.get('completion', {}).get('tasks', []):
        for requirement in task['requirements']:
            for check in requirement['checks']:
                if check['status'] != 'satisfied':
                    lines += [f"- {text(requirement['requirement_id'])}：{text(check['detail'])}"]
    if result.get('clarification'):
        lines += [text(result['clarification'])]
    lines += ['', f'[查看本次取得的完整原文与来源]({text_file.name})', '',
        '## 实际动作', '', table(['轮', '动作', '反馈', '正文累计覆盖'], [[t['turn'],
            (t.get('step') or {}).get('action', t['action']), t['feedback'],
            '；'.join(f"{r['returned_count']}/{r['required_count']}" for task in t['progress']
                     for r in task['requirements'] if r['kind'] == 'read_node') or '—']
            for t in execution.get('turns', [])]), '', '## 实际 SQL（DuckDB）', '']
    for index, item in enumerate(sql_rows, 1):
        lines += [f"### 查询 {index} · 返回 {item['returned_rows']} 行", '',
            '```sql', item['sql'], '```', '', table(['参数位置', '绑定值'],
                [[i, v] for i, v in enumerate(item['parameters'], 1)]), '']
    if not sql_rows:
        lines += ['本轮没有执行 SQL。', '']
    source_lines = ['# 本次实际取得的来源原文', '',
        '按来源去重；有原始序号的块按序号排列，缺少序号的块保留返回顺序。包含正文读取和数值出处的上下文；覆盖结论以执行报告为准。图片仅保留引用，不代表已完成 OCR。', '']
    for (sid, bid), block in sorted(blocks.items(), key=lambda item: (item[0][0],
            item[1].get('ordinal') if isinstance(item[1].get('ordinal'), int) else float('inf'))):
        source_lines += [f"## {text(sid)} · {text(bid)}", '',
            f"原刊页：{text(block.get('reported_page'))}；类型：{text(block['type'])}。", '',
            *['> ' + text(line) for line in (block.get('text') or '').splitlines()], '']
    if not blocks:
        source_lines += ['本轮没有取得来源原文。', '']
    destination.parent.mkdir(parents=True, exist_ok=True)
    with text_file.open('x') as file:
        file.write('\n'.join(source_lines))
    with destination.open('x') as file:
        file.write('\n'.join(lines))
    return destination
