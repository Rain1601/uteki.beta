"""Read-only presentation of explicitly registered, frozen query runs."""
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import re
from urllib.parse import urlencode, urlparse

from apps.review_workbench.site_navigation import bi, company_tabs, crumb, page


def e(value):
    return escape('' if value is None else str(value), quote=True)


def contained(root, name):
    target = (root / name).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError('Query artifact outside registered root')
    return target


def collections(registry, company_id):
    found = []
    for path in sorted(registry.glob('*.json')):
        item = json.loads(path.read_text())
        if item['schema_version'] != 'query-view-v1' or item['id'] != path.stem:
            raise ValueError('Unsupported query view registration')
        if item['company_id'] == company_id:
            found.append(item)
    return found


def load_case(root, collection, run_id, case_id):
    run = next((r for r in collection['runs'] if r['id'] == run_id), None)
    case = next((c for c in collection['cases'] if c['id'] == case_id), None)
    if not run or not case:
        raise KeyError('Unknown saved run or question')
    folder = contained(root, run['path'])
    selected = contained(folder, case_id)
    manifest_path = selected / 'session/manifest.json'
    if sha256(manifest_path.read_bytes()).hexdigest() != run['session_manifest_hashes'][case_id]:
        raise ValueError('Query manifest changed')
    manifest = json.loads(manifest_path.read_text())
    format_only_changes = []

    def read(relative):
        content = contained(selected / 'session', relative).read_bytes()
        value = json.loads(content)
        if sha256(content).hexdigest() != manifest['files'][relative]:
            # The writer's exact encoding is known. Accept editor whitespace
            # changes only when reconstructing those original bytes proves the
            # original hash; never rewrite the source or accept changed values.
            original_encoding = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()
            if sha256(original_encoding).hexdigest() != manifest['files'][relative]:
                raise ValueError('Saved query artifact changed')
            format_only_changes.append(relative)
        return value

    result = read('result.json')
    if set(result['request']['company_ids']) != {collection['company_id']}:
        raise ValueError('Saved query does not match company scope')
    costs_path = selected / 'costs.json'
    if sha256(costs_path.read_bytes()).hexdigest() != run['cost_hashes'][case_id]:
        raise ValueError('Saved cost artifact changed')
    costs = json.loads(costs_path.read_text())
    turns = []
    for trace in result['trace']:
        prefix = f"turn-{trace['step']:02d}/"
        values = {'trace': trace}
        for key, name in [('decision', 'decision.json'), ('result', 'tool-result.json'), ('feedback', 'feedback.json')]:
            if prefix + name in manifest['files']:
                values[key] = read(prefix + name)
        turns.append(values)
    return {'run': run, 'case': case, 'result': result, 'costs': costs, 'turns': turns,
            'format_only_changes': format_only_changes}


METRICS = {
    'revenue': ('收入', 'Revenue'), 'operating_income': ('营业利润', 'Operating income'),
    'operating_margin': ('营业利润率', 'Operating margin'),
    'capex_guidance': ('资本开支指引', 'CapEx guidance'),
    'investment_rationale': ('投资理由', 'Investment rationale'),
    'infrastructure_expense_pressure': ('基础设施费用压力', 'Infrastructure expense pressure'),
    'investment_mix_outlook': ('投资构成展望', 'Investment mix outlook'),
    'depreciation_outlook': ('折旧展望', 'Depreciation outlook'),
}
STATUSES = {'answered': ('已返回结果', 'Result returned'), 'partial': ('保留缺口', 'Gaps remain'),
            'needs_clarification': ('需要澄清', 'Clarification needed'), 'failed': ('执行失败', 'Failed'),
            'limited': ('达到执行上限', 'Limit reached'), 'unanswerable': ('无法回答', 'Unanswerable')}
GAPS = {'no_literal_match': ('关键词未命中；不表示未披露', 'No literal match; not proof of non-disclosure'),
        'target_period_unresolved': ('记录的目标期间未确定', 'Record target period unresolved'),
        'limited': ('检索达到返回上限', 'Retrieval limit reached')}


def metric(key):
    return bi(*METRICS[key]) if key in METRICS else e(key)


def period(value):
    if not value:
        return bi('未指定期间', 'No typed period')
    return e(value['start'] + ' — ' + value['end']) if value.get('start') else e(value['end'])


def number(value):
    if value is None:
        return '—'
    try:
        return format(Decimal(value), ',f')
    except InvalidOperation:
        return e(value)


def amount(record):
    if record.get('value_relation') == 'qualitative':
        return bi('定性陈述', 'Qualitative')
    signs = {'gt': '> ', 'gte': '≥ ', 'approx': '≈ '}
    value = signs.get(record.get('value_relation'), '') + number(record.get('value_decimal'))
    if record.get('upper_decimal') is not None:
        value += ' – ' + number(record['upper_decimal'])
    return value + (' ' + e(record['unit']) if record.get('unit') else '')


def evidence_details(record, evidence):
    parts = []
    for field, label in [('evidence_ids', ('原文', 'Source quote')),
                         ('qualifier_evidence_ids', ('限定条件', 'Qualifications')),
                         ('question_evidence_ids', ('分析师问题', 'Analyst question'))]:
        for eid in record.get(field, []):
            item = evidence.get(eid)
            if not item:
                parts.append('<p>' + bi('证据未随本次结果返回', 'Evidence absent from saved result') + '</p>')
                continue
            url = item.get('source_url', '')
            link = ('<a href="' + e(url) + '">' + bi('查看原始来源', 'Open original source') + '</a>') if urlparse(url).scheme in ('http', 'https') else ''
            page_no = item.get('pdf_page') or item.get('reported_page')
            parts.append('<section class="qr-citation"><strong>' + bi(*label) + '</strong><blockquote>' + e(item['quote']) +
                         '</blockquote><small>' + e(item['source_snapshot_id']) +
                         (' / p. ' + e(page_no) if page_no else '') + ' / ' + e(item['block_id']) +
                         '</small>' + link + '</section>')
    return '<details class="qr-evidence"><summary>' + bi('原文与限定', 'Evidence & qualifications') + '</summary>' + ''.join(parts) + '</details>'


def record_table(records, evidence, *, citations=True):
    if not records:
        return '<p class="qr-muted">' + bi('本步骤未返回数据行。', 'No data rows returned in this step.') + '</p>'
    rows = []
    for record in records:
        detail = ('<p class="qr-statement">' + e(record['summary']) + '</p>') if record.get('value_relation') == 'qualitative' else ''
        period_label = period(record['period']) if record['period'] else bi(*{
            'not_applicable': ('期间不适用', 'Period not applicable'),
            'unresolved': ('期间待确定', 'Period unresolved')}.get(record.get('period_resolution'), ('无类型化期间', 'No typed period')))
        speaker = '<small>' + e(record['speaker']) + '</small>' if record.get('speaker') else ''
        rows.append('<tr><td>' + metric(record['metric_id']) + '<small>' + e(record['entity_id']) + '</small>' + speaker + '</td><td>' +
                    period_label + '<small>' + bi('管理层指引', 'Management guidance') * (record['value_kind'] == 'management_guidance') +
                    '</small></td><td class="qr-value">' + amount(record) + detail +
                    (evidence_details(record, evidence) if citations else '') + '</td></tr>')
    return '<div class="qr-table-wrap"><table class="qr-table"><thead><tr>' + ''.join('<th>' + bi(*label) + '</th>' for label in
                [('指标 / 实体', 'Metric / entity'), ('期间 / 口径', 'Period / basis'), ('返回值', 'Returned value')]) + '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>'


def sql_rows(sql_trace, tool_result):
    """Match a recorded typed selection to the exact recorded bind vector.

    No rerunning SQL, guessing rows from result order, or substituting results.
    """
    for selection in tool_result.get('selections', []):
        request = selection['request']
        pairs = [('entity_id', request['entity_id']), ('metric_id', request['metric_id']), ('value_kind', request['value_kind'])]
        if request['period']:
            pairs += [('period_kind', request['period']['kind']), ('period_start', request['period']['start']), ('period_end', request['period']['end'])]
        pairs += [('available_at ≤', tool_result['knowledge_cutoff'])]
        if [v for _, v in pairs] == sql_trace['parameters']:
            ids = set(selection['record_ids'])
            return pairs, [r for r in tool_result['records'] if r['record_id'] in ids]
    return [(str(i), v) for i, v in enumerate(sql_trace['parameters'], 1)], None


def render_sql(trace, result, ordinal):
    pairs, rows = sql_rows(trace, result)
    formatted = re.sub(r'\s+(WHERE|AND|ORDER BY|LIMIT)\s+', r'\n\1 ', trace['sql']).replace(' FROM ', '\nFROM ', 1)
    return ('<section class="qr-sql"><div class="qr-row"><h4>SQL ' + str(ordinal) + '</h4><span>' + bi(
        str(trace['returned_rows']) + ' 行返回', str(trace['returned_rows']) + ' rows returned') + '</span></div><pre><code>' + e(formatted) +
        '</code></pre><details class="qr-parameters"><summary>' + bi('绑定参数', 'Bound parameters') + '</summary><dl>' + ''.join(
        '<div><dt>' + e(k) + '</dt><dd>' + e(v) + '</dd></div>' for k, v in pairs) + '</dl></details>' +
        (record_table(rows, result['evidence'], citations=False) if rows is not None else '<p>' + bi('未保存行级关联。', 'Row association not recorded.') + '</p>') + '</section>')


def render_plan(decision):
    plan = decision.get('plan')
    if not plan:
        return ''
    items = []
    for r in plan['records']:
        items.append('<li>' + bi('取数', 'Retrieve') + '：' + e(r['entity_id']) + ' / ' + metric(r['metric_id']) + ' / ' + period(r['period']) + '</li>')
    for c in plan['calculations']:
        items.append('<li>' + bi('计算', 'Calculate') + '：' + metric(c['formula_id']) + ' / ' + e(c['entity_id']) + '</li>')
    for d in plan['documents']:
        items.append('<li>' + bi('原文检索', 'Document search') + '：' + e(d['form']) + ' / ' + e(d['period_end']) + ' / “' + e(d['phrase']) + '”</li>')
    return '<ul class="qr-plan">' + ''.join(items) + '</ul>'


def render_turn(turn, first):
    trace, decision = turn['trace'], turn.get('decision', {})
    action = decision.get('action', trace['tool'])
    labels = {'query': ('查数与检索', 'Query & retrieve'), 'finish': ('提交结果引用', 'Return references'),
              'clarify': ('要求澄清', 'Ask for clarification'), 'read_context': ('回读原文', 'Read context')}
    body = render_plan(decision)
    if 'feedback' in turn:
        body += '<p class="qr-warning">' + bi('本步没有成功的 SQL 返回记录。错误：', 'No successful SQL result saved for this step. Error: ') + e(turn['feedback'].get('message') or turn['feedback']['status']) + '</p>'
    value = turn.get('result', {})
    queries = [t for t in value.get('trace', []) if t['tool'] == 'sql']
    body += ''.join(render_sql(t, value, i) for i, t in enumerate(queries, 1))
    for event in value.get('trace', []):
        if event['tool'] == 'document_search':
            body += '<p>' + bi('原文搜索', 'Document search') + ' “' + e(event['phrase']) + '”：' + e(event['total_hits']) + ' ' + bi('处匹配', 'matches') + '</p>'
    if action == 'finish':
        body += '<ul>' + ''.join('<li>' + e(p['requested_information']) + '</li>' for p in decision.get('answer_parts', [])) + '</ul><p class="qr-muted">' + bi('仅提交已返回的记录和计算引用，没有再次执行 SQL。', 'Submitted returned record/calculation references; no further SQL execution.') + '</p>'
    if action == 'clarify':
        body += '<p>' + e(decision.get('clarification')) + '</p><p class="qr-muted">' + bi('未执行 SQL。', 'No SQL executed.') + '</p>'
    if action == 'read_context':
        body += ''.join('<blockquote>' + e(b['text']) + '</blockquote>' for b in value.get('blocks', []))
    query_count = bi('SQL 轨迹未保存', 'SQL trace unavailable') if action == 'query' and 'result' not in turn else bi(str(len(queries)) + ' 次 SQL', str(len(queries)) + ' SQL queries')
    return '<details class="qr-turn"' + (' open' if first else '') + '><summary><span class="qr-step">' + str(trace['step']).zfill(2) + '</span>' + bi(*labels.get(action, (action, action))) + '<span class="qr-step-note">' + query_count + '</span></summary><div class="qr-turn-body">' + body + '</div></details>'


def view_url(company_id, collection, run, case):
    return '/companies/' + company_id + '/data/queries?' + urlencode({'collection': collection, 'run': run, 'case': case})


def render_query_runs(root, registry, company, selection):
    registered = collections(registry, company['id'])
    chrome = crumb(company, ('查询与结果', 'Queries & results')) + company_tabs(company['id'], 'data')
    chrome += '<style>' + Path(__file__).with_suffix('.css').read_text() + '</style><div class="qr-workspace">'
    if not selection:
        body = '<h1>' + bi('查询与结果', 'Queries & results') + '</h1><p>' + bi('选择已保存的查询，查看实际 SQL 与返回记录。', 'Select a saved query to inspect its SQL and returned records.') + '</p>'
        for item in registered:
            body += '<h2>' + bi(*item['label']) + '</h2><ul class="qr-directory">'
            if item.get('dataset'):
                body += '<li><a href="/companies/' + e(company['id']) + '/data/dataset?' + e(urlencode({'collection': item['id']})) + '">' + bi('数据库明细与处理过程', 'Database records & lineage') + '</a></li>'
            for run in item['runs']:
                for case in item['cases']:
                    body += '<li><a href="' + e(view_url(company['id'], item['id'], run['id'], case['id'])) + '">' + bi(*run['label']) + ' / ' + bi(*case['label']) + '</a></li>'
            body += '</ul>'
        if not registered:
            body += '<p>' + bi('此公司尚无已登记的查询运行。', 'No registered query runs for this company.') + '</p>'
        return page('查询与结果', chrome + body + '</div>')
    collection = next((c for c in registered if c['id'] == selection['collection']), None)
    if not collection:
        raise KeyError('Unknown company query collection')
    try:
        data = load_case(root, collection, selection['run'], selection['case'])
    except (ValueError, OSError):
        message = '<h1>' + bi('查询记录暂不可展示', 'Saved query unavailable') + '</h1><p>' + bi('文件缺失或内容与登记指纹不一致，未展示未经核验的结果。', 'Files are missing or fail registered integrity checks; unverified results are not displayed.') + '</p><a href="/companies/' + e(company['id']) + '/data/queries">' + bi('选择其他查询', 'Choose another query') + '</a>'
        return page('查询记录校验', chrome + message + '</div>')
    result, costs = data['result'], data['costs']
    sidebar = '<aside class="qr-sidebar"><h2>' + bi('已运行的问题', 'Saved questions') + '</h2><nav aria-label="Saved questions">'
    for case in collection['cases']:
        sidebar += '<a' + (' aria-current="page"' if case['id'] == selection['case'] else '') + ' href="' + e(view_url(company['id'], collection['id'], selection['run'], case['id'])) + '">' + bi(*case['label']) + '</a>'
    sidebar += '</nav><p class="qr-muted">' + bi('读取已保存的真实运行。切换或展开不会调用模型。', 'Saved live runs. Browsing does not call a model.') + '</p>'
    if collection.get('dataset'):
        sidebar += '<p><a href="/companies/' + e(company['id']) + '/data/dataset?' + e(urlencode({'collection': collection['id']})) + '">' + bi('数据库明细与处理过程', 'Database records & lineage') + '</a></p>'
    sidebar += '<a href="/companies/' + e(company['id']) + '/data">' + bi('返回结构化数据', 'Back to structured data') + '</a></aside>'
    main = '<article class="qr-main"><div class="qr-row"><h1>' + bi('查询与结果', 'Queries & results') + '</h1><nav class="qr-runs" aria-label="Run versions">'
    for run in collection['runs']:
        main += '<a' + (' aria-current="page"' if run['id'] == selection['run'] else '') + ' href="' + e(view_url(company['id'], collection['id'], run['id'], selection['case'])) + '">' + bi(*run['label']) + '</a>'
    main += '</nav></div><p class="qr-question">' + e(result['request']['question']) + '</p>'
    main += '<div class="qr-meta"><span class="qr-status">' + bi(*STATUSES.get(result['status'], (result['status'], result['status']))) + '</span><span>' + bi('候选数据 · 未采纳', 'Candidate data · not adopted') + '</span><span>' + bi('截至 ', 'As of ') + e(result['request']['knowledge_cutoff']) + '</span></div>'
    note = data['case'].get('review_notes', {}).get(selection['run'])
    if note:
        main += '<p class="qr-review">' + bi('核验备注：', 'Review note: ') + bi(*note) + '</p>'
    main += '<section class="qr-results"><h2>' + bi('返回结果', 'Returned results') + '</h2>'
    if result['clarification']:
        main += '<p class="qr-clarification">' + e(result['clarification']) + '</p>'
    quantitative = [r for r in result['records'] if r.get('value_relation') != 'qualitative']
    qualitative = [r for r in result['records'] if r.get('value_relation') == 'qualitative']
    if quantitative or not (qualitative or result['contexts']):
        main += record_table(quantitative, result['evidence'])
    if qualitative:
        main += '<details class="qr-extra"><summary>' + bi(f'定性记录（{len(qualitative)} 条）', f'Qualitative records ({len(qualitative)})') + '</summary>' + record_table(qualitative, result['evidence']) + '</details>'
    if result['contexts']:
        main += '<details class="qr-extra"><summary>' + bi(f'检索返回的原文（{len(result["contexts"])} 组）', f'Retrieved source contexts ({len(result["contexts"])})') + '</summary>'
        for context in result['contexts']:
            main += '<section class="qr-citation"><small>' + e(context['source_snapshot_id']) + '</small>'
            main += ''.join('<blockquote>' + e(block['text']) + '</blockquote><small>' + e(block['block_id']) + '</small>' for block in context['blocks']) + '</section>'
        main += '</details>'
    record_map = {r['record_id']: r for r in result['records']}
    for fact in result['computed_facts']:
        main += '<div class="qr-calculation"><div><strong>' + metric(fact['formula_id'].removesuffix('-v1')) + '</strong><small>' + e(fact['entity_id']) + ' / ' + ' / '.join(period(p) for p in fact['periods']) + '</small></div><b>' + e(fact['display_decimal']) + ('%' if fact['unit'] == 'percent' else ' ' + e(fact['unit'])) + '</b></div>'
        main += '<p class="qr-muted">' + bi('Python Decimal 计算；输入来自上述 SQL 记录。', 'Calculated with Python Decimal from SQL records.') + '</p><details><summary>' + bi('计算依据与精度', 'Operands & precision') + '</summary>'
        main += record_table([record_map[rid] for rid in fact['operand_record_ids'] if rid in record_map], result['evidence'], citations=False)
        main += '<p>' + e(fact['formula_id']) + ' / ' + e(fact['rounding']) + '</p></details>'
    if result['gaps']:
        main += '<div class="qr-gaps"><h3>' + bi('本次保留的缺口', 'Retained gaps') + '</h3><ul>' + ''.join('<li>' + bi(*GAPS.get(g['reason'], (g['reason'], g['reason']))) + '</li>' for g in result['gaps']) + '</ul></div>'
    main += '</section><section class="qr-process"><div class="qr-row"><h2>' + bi('查询过程', 'Query process') + '</h2><span class="qr-muted">' + bi('计划 → SQL → 返回行', 'Plan → SQL → rows') + '</span></div>'
    main += ''.join(render_turn(t, i == 0) for i, t in enumerate(data['turns'])) + '</section>'
    format_note = '<p>' + bi('部分历史文件仅排版变化；按原写入格式还原后的指纹一致，未改写原文件。', 'Some historical files were reformatted; original-encoding hashes match. Source files were not rewritten.') + '</p>' if data['format_only_changes'] else ''
    main += '<footer class="qr-footer"><span>' + bi('模型请求 ', 'Model requests ') + str(costs['requests']) + ' / ' + bi('估算费用 ', 'Estimated cost ') + 'USD ' + e(costs['known_estimated_usd']) + '</span><details><summary>' + bi('数据版本与计量', 'Snapshot & metering') + '</summary><p>' + e(result['request']['snapshot_id']) + '</p><p>' + bi('未知费用请求：', 'Requests with unknown cost: ') + str(costs['unknown_cost_requests']) + ' / ' + bi('公开单价估算，非供应商账单。', 'List-price estimate, not a provider bill.') + '</p>' + format_note + '</details></footer></article>'
    return page('查询与结果', chrome + '<div class="qr-layout">' + sidebar + main + '</div></div>')
