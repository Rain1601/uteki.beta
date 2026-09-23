"""Read-only walkthrough of explicitly registered, hash-pinned offline replays.

This view never invokes an agent, SQL executor, model, source fetch, or adoption.
Editorial explanations are separate from the saved request and returned evidence.
"""
from apps.review_workbench.assets import asset_text
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import quote, urlencode, urlparse

from apps.review_workbench.pages.dataset_view import compare, field_table, render_block
from apps.review_workbench.pages.query_runs import contained, e, amount, metric, period, record_table
from apps.review_workbench.components.site_navigation import bi, company_tabs, crumb, page
from uteki.domain.research_data.evidence_package import EvidencePackage


KINDS = {
    'source_text': ('解析原文', 'Parsed source text'),
    'source_table': ('解析表格', 'Parsed source table'),
    'source_quote': ('定位引文', 'Located quotation'),
    'image_reference': ('图片引用', 'Image reference'),
    'normalized_record': ('规范化记录', 'Normalized record'),
    'computed_scalar': ('计算结果', 'Computed value'),
    'model_extract': ('历史模型提取', 'Historical model extraction'),
    'model_summary': ('模型摘要', 'Model summary'),
}
ACTIONS = {
    'outline_source': ('查看目录', 'Inspect outline'),
    'read_source': ('读取选定内容', 'Read selected content'),
    'query': ('取数与计算', 'Query & calculate'),
    'finish': ('提交已有引用', 'Return references'),
}
GAPS = {
    'image_bytes_unavailable': ('图片字节缺失：仅有引用，未进行 OCR 或视觉理解。', 'Image bytes unavailable: reference only; no OCR or visual understanding.'),
    'region_units_unverified': ('图片/文本区域坐标的单位未经确认，不能精确框选引文。', 'Region coordinate units are unverified; boxes do not precisely locate quotes.'),
    'model_metadata_unavailable': ('历史模型的供应商、型号和 prompt 指纹缺失。', 'Historical provider, model and prompt hashes are unavailable.'),
}


def registrations(registry, company_id):
    entries = []
    for file in sorted(registry.glob('*.json')):
        item = json.loads(file.read_text())
        if item['schema_version'] != 'acceptance-view-v1' or item['id'] != file.stem:
            raise ValueError('Unsupported acceptance registration')
        if item['company_id'] == company_id:
            entries.append(item)
    return entries


def pinned_json(folder, name, digest):
    content = contained(folder, name).read_bytes()
    if sha256(content).hexdigest() != digest:
        raise ValueError('Acceptance artifact changed: ' + name)
    return json.loads(content)


def matches(expected, actual):
    """Replay decisions allow serializer defaults, but no changed explicit input."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and matches(v, actual[k]) for k, v in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(expected) == len(actual) and all(matches(a, b) for a, b in zip(expected, actual))
    return expected == actual


def load_walkthrough(root, registration):
    run = contained(root, registration['run']['path'])
    session = contained(run, 'session')
    manifest = pinned_json(session, 'manifest.json', registration['run']['manifest_sha256'])
    saved = {name: pinned_json(session, name, digest) for name, digest in manifest['files'].items()}
    spec = pinned_json(run, 'spec.json', registration['run']['spec_sha256'])
    verification = pinned_json(run, 'verification.json', registration['run']['verification_sha256'])
    checks = pinned_json(run, 'final-verification.json', registration['run']['final_verification_sha256'])
    if verification['mode'] != 'scripted_offline_tools' or verification['model_calls'] != 0 or checks['model_calls'] != 0:
        raise ValueError('This viewer requires a recorded offline scripted replay')
    folder = contained(root, registration['dataset']['path'])
    dataset_manifest = pinned_json(folder, 'manifest.json', registration['dataset']['manifest_sha256'])
    for name, digest in dataset_manifest['files'].items():
        if sha256(contained(folder, name).read_bytes()).hexdigest() != digest:
            raise ValueError('Dataset artifact changed: ' + name)
    def dataset_json(name):
        return pinned_json(folder, name, dataset_manifest['files'][name])
    request, result, package = (saved[name] for name in ('request.json', 'result.json', 'evidence-package.json'))
    EvidencePackage.model_validate(package)
    scope = request['scope']
    if (scope['company_ids'] != [registration['company_id']]
            or scope != package['scope'] or result['request'] != request
            or scope['snapshot_id'] != dataset_manifest['snapshot_id']
            or not matches(spec['request'], request)
            or contained(root, spec['dataset']) != folder
            or result['evidence_package']['bundle_id'] != package['bundle_id']):
        raise ValueError('Inconsistent acceptance scope')
    sources = {s['source_snapshot_id']: s for s in dataset_json('sources.json')}
    selected = [sources[sid] for sid in scope['source_snapshot_ids']]
    if any(s['company_id'] != registration['company_id'] or s['available_at'] > scope['knowledge_cutoff'] for s in selected):
        raise ValueError('Source outside acceptance scope')
    turns = []
    if len(spec['steps']) != len(result['trace']):
        raise ValueError('Replay step count mismatch')
    for ordinal, (step, trace) in enumerate(zip(spec['steps'], result['trace']), 1):
        prefix = f'turn-{ordinal:02d}'
        decision = saved[prefix + '/decision.json']
        if trace['step'] != ordinal or trace['tool'] != decision['action'] or decision['action'] not in ACTIONS:
            raise ValueError('Unsupported or inconsistent replay step')
        if ('decision' in step and not matches(step['decision'], decision)) or ('finish_references' in step and decision['action'] != 'finish'):
            raise ValueError('Script differs from saved decision')
        tool_result = saved.get(prefix + '/tool-result.json')
        if decision['action'] != 'finish':
            if trace.get('result_file') != prefix + '/tool-result.json' or tool_result is None:
                raise ValueError('Missing recorded tool result')
        turns.append({'step': ordinal, 'decision': decision, 'result': tool_result})
    records = [r for r in dataset_json('records.json')['rows']
               if r['source_snapshot_id'] in scope['source_snapshot_ids']
               and r['available_at'] <= scope['knowledge_cutoff'] and scope['include_candidates']]
    return dict(registration=registration, request=request, result=result, package=package,
                turns=turns, sources=selected, records=records, checks=checks,
                excluded=[s for s in sources.values() if s['company_id'] == registration['company_id'] and s['source_snapshot_id'] not in scope['source_snapshot_ids']])


def details(title, body, opened=False):
    return '<details' + (' open' if opened else '') + '><summary>' + bi(*title) + '</summary><div class="av-disclosure">' + body + '</div></details>'


def table(headers, rows):
    return '<div class="av-scroll"><table><thead><tr>' + ''.join('<th>' + bi(*h) + '</th>' for h in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + cell + '</td>' for cell in row) + '</tr>' for row in rows) + '</tbody></table></div>'


def note(zh, en):
    return '<p class="av-note">' + bi(zh, en) + '</p>'


def source_link(source):
    url = source.get('source_url', '')
    form = source.get('form', '')
    label = bi(*{'10-K': ('年报 10-K', 'Annual report 10-K'), '10-Q': ('季报 10-Q', 'Quarterly report 10-Q'),
                 'EARNINGS_CALL': ('电话会文字稿', 'Earnings call transcript')}.get(form, (form, form)))
    label += ' · ' + e(source.get('period_end', ''))
    if urlparse(url).scheme in ('http', 'https'):
        return '<a href="' + e(url) + '">' + label + ' ↗</a>'
    return label


def locator(loc):
    parts = [loc.get('block_id')]
    if loc.get('pdf_page') is not None:
        parts.append('PDF p. ' + str(loc['pdf_page']))
    if loc.get('reported_page') is not None:
        parts.append('p. ' + str(loc['reported_page']))
    return '<small class="av-meta">' + e(' · '.join(str(p) for p in parts if p is not None)) + '</small>'


def source_table(sources):
    return table([('材料 / 报告期', 'Source / period'), ('公开日期', 'Available from'), ('版本', 'Version')], [
        [source_link(s), e(s['available_at']), '<code>' + e(s['source_snapshot_id']) + '</code>'] for s in sources])


def input_panel(data):
    scope = data['request']['scope']
    body = '<h2>' + bi('先确认：这轮拿什么来处理', 'First: what this run starts with') + '</h2>'
    body += note('输入是已经解析的文档块、已有候选数据库和预设步骤。原始材料在更早阶段已解析；这轮没有重新提取整份年报。', 'Inputs are previously parsed blocks, an existing candidate database and scripted steps. Parsing happened earlier; this run did not re-extract the annual report.')
    body += source_table(data['sources'])
    body += '<h3>' + bi('执行条件', 'Execution conditions') + '</h3>'
    body += table([('条件', 'Condition'), ('本轮实际设置', 'Actual setting')], [
        [bi('可用信息截止日', 'Knowledge cutoff'), e(scope['knowledge_cutoff'])],
        [bi('候选数据', 'Candidate records'), bi('允许使用；尚未人工采纳', 'Included; not human-adopted') if scope['include_candidates'] else bi('不允许', 'Excluded')],
        [bi('数据快照', 'Dataset snapshot'), '<code>' + e(scope['snapshot_id']) + '</code>'],
        [bi('步骤由谁决定', 'Who selects steps'), bi('预设脚本；没有本轮模型规划或新模型提取', 'A predefined script; no live model planning or new model extraction')],
        [bi('允许的来源', 'Allowed sources'), bi('只使用上表明确选定的版本', 'Only the explicitly selected versions above')],
    ])
    if data['excluded']:
        body += details(('数据库里还有、但本轮未使用的来源', 'Sources in the database but excluded from this run'), source_table(data['excluded']))
    body += '<h3>' + bi('输入数据长什么样', 'What the input data looks like') + '</h3>'
    body += '<p>' + bi(f"选定来源中有 {len(data['records'])} 条已有记录；下方是本轮可取的候选输入，不代表每条都被查询。", f"The selected sources contain {len(data['records'])} existing records. These are available inputs, not all retrieved rows.") + '</p>'
    body += details(('查看候选输入表', 'Inspect candidate input table'), record_table(data['records'], {}, citations=False))
    body += details(('查看实际提交的问题', 'Inspect the exact submitted question'), '<blockquote>' + e(data['request']['question']) + '</blockquote>')
    body += note('核对方式：先确认材料、报告期和截止日，再点左侧步骤。业务数字、原话、单位、条件都可以继续展开核对。', 'Review the sources, reporting periods and cutoff, then select a step. Expand values, original wording, units and qualifications to check them.')
    return body


def read_panel(decision, result, turns):
    read = decision['read']
    body = '<h3>' + bi('输入与动作', 'Input & action') + '</h3><p>' + source_link(result['source']) + '</p>'
    node = next((n for turn in turns if turn['decision']['action'] == 'outline_source'
                 and turn['decision']['outline']['source_snapshot_id'] == read['source_snapshot_id']
                 for n in turn['result']['nodes'] if n['node_id'] == read['node_id']), None)
    node_title = e(node['title']) if node and node['kind'] != 'document' else bi('全文索引中的指定位置', 'Selected location in the document index')
    body += table([('读取范围', 'Read scope'), ('请求数量', 'Requested count')], [[node_title, bi(f"{read['count']} 个块", f"{read['count']} blocks")]])
    body += details(('精确起点与工具参数', 'Exact start & tool parameters'), field_table({k: v for k, v in read.items() if v is not None}))
    body += '<p>' + bi('从已冻结的解析索引读取指定章节/起点，保留原块及定位。此步没有模型改写。', 'Read the selected node/start from the frozen index, preserving blocks and locators. No model rewriting in this step.') + '</p>'
    body += '<h3>' + bi('实际返回', 'Actual return') + '</h3>'
    for block in result['blocks']:
        body += '<div class="av-source">' + locator(block)
        if block['type'] == 'image':
            body += '<p>' + bi('图片引用 · 替代文字：', 'Image reference · alt text: ') + '<code>' + e(block['text']) + '</code></p>'
            body += note('这不是正文或 OCR 结果。只有图片标识与替代文字，不能据此解释图中内容。', 'This is neither prose nor OCR output. The ID and alt text do not establish image content.')
        else:
            body += '<small>' + bi(*(('标题', 'Heading') if block['type'] == 'heading_candidate' else ('表格', 'Table') if block.get('table') else ('正文', 'Text'))) + '</small>'
            body += render_block(block) if block.get('table') else '<blockquote>' + e(block['text']) + '</blockquote>'
        if block.get('speaker'):
            body += '<small>' + e(block['speaker']) + '</small>'
        body += '</div>'
    body += note('核对方式：原文是否保持完整、页码和类型是否正确？返回几块只说明读取量，不等于形成几条结论。', 'Check the exact wording, pages and content types. Returned blocks measure retrieval, not research conclusions.')
    continuation = ('后面还有内容，可继续读取。', 'More content remains available for reading.') if result.get('next_cursor') else ('没有后续游标；这不证明前文已读。', 'No next cursor; earlier text may still be unread.')
    body += '<p>' + bi(*continuation)
    return body + '</p>' + details(('续读位置与覆盖状态', 'Continuation & coverage'), field_table({k: result.get(k) for k in ('node_complete', 'next_cursor', 'coverage')}))


def record_lineage(record, evidence):
    body = '<p>' + e(record['entity_id']) + ' / ' + metric(record['metric_id']) + ' / ' + period(record['period']) + '</p>'
    for key, labels in [('evidence_ids', ('取值原文', 'Value evidence')), ('qualifier_evidence_ids', ('限定条件', 'Qualifications'))]:
        for eid in record.get(key, []):
            ev = evidence[eid]
            body += '<div class="av-source"><strong>' + bi(*labels) + '</strong><blockquote>' + e(ev['quote']) + '</blockquote>' + locator(ev)
            if ev.get('number_metadata'):
                body += field_table(ev['number_metadata'])
            body += '</div>'
    body += '<h4>' + bi('更早阶段的提取 → 规范化入库', 'Earlier extraction → database normalization') + '</h4>'
    body += compare(record)
    body += '<p>' + bi('本轮读取这些已有值；历史提取与规范化没有重新执行。', 'This run retrieved existing values; the historical extraction and normalization were not rerun.') + '</p>'
    return body + details(('原始提取记录与规范化说明', 'Original extraction & normalization notes'), field_table(record['origin']) + '<ul>' + ''.join('<li>' + e(x) + '</li>' for x in record.get('normalization_notes', [])) + '</ul>')


def query_panel(decision, result):
    body = '<h3>' + bi('输入：本步要取什么', 'Input: what this step requests') + '</h3>'
    requests = [[bi('取数', 'Retrieve'), e(r['entity_id']) + ' / ' + metric(r['metric_id']), period(r['period'])]
                for r in decision['plan'].get('records', [])]
    requests += [[bi('计算', 'Calculate'), e(c['entity_id']) + ' / ' + metric(c['formula_id']), '<br>'.join(period(p) for p in c['periods'])]
                 for c in decision['plan'].get('calculations', [])]
    body += table([('动作', 'Action'), ('对象与指标', 'Entity & metric'), ('期间', 'Period')], requests)
    body += note('预设的结构化请求交给 SQL generator 生成带参数的 SQL，executor 在限定快照中执行；注册公式再使用返回记录计算。', 'The scripted typed request goes to the SQL generator, then the executor queries the scoped snapshot. Registered formulas calculate from returned records.')
    body += '<h3>' + bi('实际返回的数据库行', 'Actual database rows returned') + '</h3>' + record_table(result['records'], result['evidence'], citations=False)
    body += note('同一指标可能包含多次披露。行数不是独立事实数；指引也不是已经发生的财务实绩。', 'A metric may have multiple disclosures. Rows are not independent facts; guidance is not an actual financial result.')
    for record in result['records']:
        title = record['entity_id'] + ' / ' + record['metric_id'] + (' / ' + record['speaker'] if record.get('speaker') else '')
        body += details(('核对来源与前后字段：' + title, 'Source & field comparison: ' + title), record_lineage(record, result['evidence']))
    body += '<h3>' + bi('计算结果', 'Calculated results') + '</h3>'
    by_id = {r['record_id']: r for r in result['records']}
    for fact in result.get('computed_facts', []):
        body += '<div class="av-calculation"><strong>' + e(fact['display_decimal']) + ' ' + e(fact['unit']) + '</strong><p>' + e(fact['entity_id']) + ' · ' + e(fact['formula_id']) + '</p>'
        operands = [by_id[r] for r in fact['operand_record_ids']]
        if fact['formula_id'] == 'operating_margin-v1':
            metrics = {r['metric_id']: r for r in operands}
            body += '<p>' + amount(metrics['operating_income']) + ' ÷ ' + amount(metrics['revenue']) + ' × 100 = ' + e(fact['value_decimal']) + '%</p>'
        body += details(('计算输入、精度与公式编号', 'Operands, precision & formula ID'), field_table(fact)) + '</div>'
    traces = [t for t in result['trace'] if t['tool'] == 'sql']
    sql = ''
    for i, trace in enumerate(traces, 1):
        formatted = trace['sql'].replace(' WHERE ', '\nWHERE ').replace(' AND ', '\n  AND ').replace(' ORDER BY ', '\nORDER BY ')
        sql += '<h4>SQL ' + str(i) + ' · ' + bi(f"返回 {trace['returned_rows']} 行", f"{trace['returned_rows']} rows returned") + '</h4><pre><code>' + e(formatted) + '</code></pre>'
        sql += table([('参数位置', 'Parameter position'), ('绑定值', 'Bound value')], [[e(j), e(v)] for j, v in enumerate(trace['parameters'], 1)])
    body += details(('展开实际 SQL 与绑定参数', 'Inspect actual SQL & bound parameters'), sql)
    return body + note('核对方式：先看金额对应的期间、单位和发言人，再核对引文中的条件；计算结果可以用上方两个输入复算。', 'Check periods, units and speakers, then the qualifications in each quote. Recalculate using the two operands above.')


def turn_label(turn):
    if turn['decision']['action'] != 'read_source':
        return ACTIONS[turn['decision']['action']]
    blocks = turn['result']['blocks']
    if blocks and all(b['type'] == 'image' for b in blocks):
        return ('读取图片引用', 'Read image reference')
    form = turn['result']['source']['form']
    return {'10-K': ('读取年报正文', 'Read annual report'),
            '10-Q': ('读取季报正文', 'Read quarterly report'),
            'EARNINGS_CALL': ('读取电话会正文', 'Read call transcript')}.get(form, ACTIONS['read_source'])


def turn_panel(turn, turns):
    decision, result = turn['decision'], turn['result']
    action = decision['action']
    body = '<h2>' + e(f"{turn['step']:02d}") + ' · ' + bi(*turn_label(turn)) + '</h2>'
    if action == 'read_source':
        return body + read_panel(decision, result, turns)
    if action == 'query':
        return body + query_panel(decision, result)
    if action == 'outline_source':
        body += '<h3>' + bi('输入与动作', 'Input & action') + '</h3><p>' + source_link(result['source']) + '</p>'
        body += '<p>' + bi('读取指定版本的文档目录，用章节起止位置为后续读取导航。', 'Read the selected version’s outline and chapter boundaries for later navigation.') + '</p>'
        body += '<h3>' + bi(f"返回 {len(result['nodes'])} 个目录节点", f"Returned {len(result['nodes'])} outline nodes") + '</h3>'
        body += table([('章节标题（原文）', 'Original heading'), ('起始页', 'Start page'), ('范围', 'Block range')], [[e(n['title']), e(n.get('reported_page')), e(n.get('start_block_id')) + '<br>' + e(n.get('end_block_id'))] for n in result['nodes']])
        return body + note('核对方式：可以找到章节及位置；但本步没有返回正文。看到 Risk Factors 目录，不代表风险因素已经读完。', 'The outline provides locations, not body text. A Risk Factors heading does not mean its contents were read.')
    body += '<p>' + bi('输入是前面已经返回的记录、计算和上下文 ID。本步提交引用，不再取数或生成研究分析。', 'Inputs are IDs of earlier records, calculations and contexts. This step returns references without further retrieval or research analysis.') + '</p>'
    body += details(('提交了哪些引用', 'Submitted references'), field_table(decision['answer_parts']), True)
    return body + note('“answered”只记录引用循环结束。证据缺口和研究是否完整，必须继续看「交付与缺口」。', '“answered” records the reference loop ending. Continue to Output & gaps to review missing evidence and research completeness.')


def artifact_body(artifact):
    payload, kind = artifact['payload'], artifact['kind']
    body = ''.join(locator(loc) for loc in artifact['locators'])
    if kind == 'source_table':
        body += render_block({'text': payload['text'], 'table': payload['table']})
    elif kind in ('source_text', 'source_quote'):
        body += '<blockquote>' + e(payload['text']) + '</blockquote>'
    elif kind == 'normalized_record':
        record = payload['record']
        body += '<p>' + e(record['entity_id']) + ' / ' + metric(record['metric_id']) + ' / ' + amount(record) + '</p>'
    else:
        body += field_table(payload)
    body += details(('来源方式与上游引用', 'Provenance & parent references'), field_table({'artifact_id': artifact['artifact_id'], 'derived_from': artifact['derived_from'], 'provenance': artifact['provenance']}))
    return body


def artifact_title(artifact):
    kind, payload = artifact['kind'], artifact['payload']
    pages = list(dict.fromkeys('PDF p. ' + str(loc['pdf_page']) if loc.get('pdf_page') is not None
                              else 'p. ' + str(loc['reported_page']) for loc in artifact['locators']
                              if loc.get('pdf_page') is not None or loc.get('reported_page') is not None))
    place = ' · '.join(pages)
    if kind in ('source_text', 'source_quote'):
        text = payload['text']
        return (text[:90] + '…' if len(text) > 90 else text) + (' · ' + place if place else '')
    if kind == 'source_table':
        return place or artifact['artifact_id']
    if kind == 'normalized_record':
        record = payload['record']
        return record['entity_id'] + ' / ' + record['metric_id']
    if kind == 'computed_scalar':
        fact = payload['fact']
        return fact['entity_id'] + ' / ' + fact['formula_id'] + ' / ' + fact['display_decimal']
    if kind == 'model_extract':
        extraction = payload['extraction']
        return ' · '.join(str(extraction[k]) for k in ('entity', 'metric', 'period', 'speaker') if extraction.get(k)) or artifact['artifact_id']
    return place or artifact['artifact_id']


def output_panel(data):
    package, result = data['package'], data['result']
    counts = Counter(a['kind'] for a in package['artifacts'])
    body = '<h2>' + bi('交付：把分散返回组织为可追溯的证据包', 'Output: traceable evidence from separate tool returns') + '</h2>'
    count = len(data['turns'])
    body += note(f'这是 {count} 次决策结束后，由宿主执行的打包与校验。页面只读取保存结果，不会重新运行。', f'Packaging and validation ran in the host after {count} decisions. This page reads saved results only.')
    body += table([('打包前', 'Before packaging'), ('本阶段新增', 'Added in this phase')], [
        [bi('文本块、表格、记录、计算分散在工具返回中', 'Text, tables, records and calculations in separate returns'), bi('统一类型、来源定位与派生引用，后续 Agent 可按类型消费', 'Typed artifacts, source locators and parent references for downstream agents')],
        [bi('只看 answered，容易误解为完成研究', '“answered” alone may imply completed research'), bi('分别保存阅读覆盖、证据缺口、语义完整性状态', 'Separate reading coverage, evidence gaps and semantic completeness')],
        [bi('已有候选数值与历史提取', 'Existing candidate values and historical extractions'), bi('数值仍来自已有记录；打包本身不提高提取准确率', 'Values retain their origin; packaging alone does not improve extraction accuracy')],
    ])
    body += '<h3>' + bi(f"{len(package['artifacts'])} 个产物，可以逐项展开", f"{len(package['artifacts'])} artifacts, inspectable by type") + '</h3>'
    body += '<p>' + bi('多种表示可能描述同一事实，不相加为事实数。表格是已解析结构，不是原网页截图。', 'Multiple representations may describe the same fact. Parsed tables are not screenshots of the original page.') + '</p>'
    for kind, labels in KINDS.items():
        artifacts = [a for a in package['artifacts'] if a['kind'] == kind]
        content = ''.join(details((artifact_title(a), artifact_title(a)), artifact_body(a)) for a in artifacts) or '<p>' + bi('本轮没有此类产物。', 'No artifacts of this type in this run.') + '</p>'
        body += details((f'{labels[0]} · {counts[kind]}', f'{labels[1]} · {counts[kind]}'), content)
    body += '<h3>' + bi('实际看了多少内容', 'What was actually returned to the agent') + '</h3>'
    coverage = package['coverage']
    modes = {
        'body_returned': ('正文返回（含标题）', 'Body returned (including headings)'),
        'image_reference_only': ('仅图片引用', 'Image references only'),
        'provenance_only': ('仅为核对出处加载', 'Loaded only to verify provenance'),
        'navigation_only': ('仅导航', 'Navigation only'),
    }
    rows = []
    for mode, labels in modes.items():
        blocks = {(c['source_snapshot_id'], b) for c in coverage if c['mode'] == mode for b in c['block_ids']}
        rows.append([bi(*labels), e(len(blocks)) if mode != 'navigation_only' else bi('不返回正文', 'No body text')])
    body += table([('覆盖类型', 'Coverage type'), ('去重块数', 'Unique blocks')], rows)
    body += note('上述范围可能重叠，不能相加。为核对出处加载的原文，不自动计为 Agent 已阅读。', 'These sets may overlap and must not be added. Provenance-only content does not count as agent reading.')
    body += '<h3>' + bi('结果成立到什么程度', 'What the result establishes') + '</h3>'
    body += table([('检查', 'Check'), ('实际状态', 'Actual status')], [
        [bi('本页输入文件完整性', 'Input file integrity in this view'), bi('已校验登记指纹与快照文件', 'Registered hashes and snapshot files verified')],
        [bi('引用循环', 'Reference loop'), e(result['status']) + ' · ' + bi(f"运行缺口 {len(result['gaps'])}", f"{len(result['gaps'])} run gaps")],
        [bi('证据包', 'Evidence package'), bi(f"保留 {len(package['gaps'])} 个缺口，详见下方", f"{len(package['gaps'])} gaps retained below")],
        [bi('是否足以回答完整研究问题', 'Completeness of research answer'), bi('未评估', 'Not evaluated') if package['semantic_completeness'] == 'not_evaluated' else e(package['semantic_completeness'])],
        [bi('自主拆解大问题', 'Autonomous task decomposition'), bi('本样例未验证，仍在下一阶段 TODO', 'Not tested here; planned for the next phase')],
    ])
    for gap in package['gaps']:
        body += '<div class="av-gap"><p>' + bi(*GAPS.get(gap['reason'], (gap['detail'], gap['detail']))) + '</p>' + details(('受影响对象与原始说明', 'Affected artifacts & recorded detail'), field_table(gap)) + '</div>'
    body += details(('该次运行保存的工程检查（不是人工验收）', 'Saved engineering checks (not human acceptance)'), field_table(data['checks']['checks']))
    return body + note('你可以据此核对数值、来源与处理边界；全文遗漏多少、提取语义是否充分，仍需另外设计验收，不能由产物数量证明。', 'You can review values, sources and processing limits here. Full-document recall and semantic adequacy need separate evaluation; artifact counts cannot establish either.')


def render_acceptance(root, registry, company, collection_id=None):
    entries = registrations(registry, company['id'])
    body = crumb(company, ('步骤验收', 'Step walkthrough')) + company_tabs(company['id'], 'data')
    if collection_id is None:
        body += '<h1>' + bi('步骤验收', 'Step walkthrough') + '</h1><p>' + bi('选择一个明确登记的运行，查看输入、过程与交付。', 'Select a registered run to inspect its inputs, process and output.') + '</p>'
        for item in entries:
            url = '/companies/' + quote(company['id'], safe='') + '/data/acceptance?' + urlencode({'collection': item['id']})
            body += '<p><a href="' + e(url) + '">' + bi(*item['title']) + '</a></p>'
        if not entries:
            body += '<p>' + bi('此公司还没有登记验收样例。', 'No acceptance runs registered for this company.') + '</p>'
        return page('步骤验收', body)
    registration = next((item for item in entries if item['id'] == collection_id), None)
    if registration is None:
        raise KeyError('Unknown company acceptance selection')
    data = load_walkthrough(root, registration)
    body += '<div class="av-heading"><div><p class="av-eyebrow">' + bi('DATA AGENT · 步骤验收', 'DATA AGENT · STEP WALKTHROUGH') + '</p><h1>' + bi(*registration['title']) + '</h1></div><span class="av-mode">' + bi('离线脚本 · 本轮 0 次模型调用', 'Scripted offline · 0 model calls') + '</span></div>'
    body += '<p class="av-intro">' + bi('本阶段把已有文本、数值和图片引用组织为统一证据包。先核对输入，再逐步看真实返回，最后检查缺口。', 'This phase organizes existing text, values and image references into an evidence package. Inspect the input, follow the actual returns, then review the gaps.') + '</p>'
    panels = [('input', ('输入与条件', 'Input & conditions'), input_panel(data))]
    panels += [(f"step-{t['step']}", (f"{t['step']:02d}  {turn_label(t)[0]}", f"{t['step']:02d}  {turn_label(t)[1]}"), turn_panel(t, data['turns'])) for t in data['turns']]
    panels += [('output', ('交付与缺口', 'Output & gaps'), output_panel(data))]
    body += '<div class="av-layout" id="walkthrough"><nav class="av-steps" aria-label="Walkthrough steps">' + ''.join('<a data-av-step="' + key + '" href="#' + key + '">' + bi(*label) + '</a>' for key, label, _ in panels) + '</nav><div class="av-content">'
    body += ''.join('<section class="av-panel" id="' + key + '" aria-label="' + e(label[0] + ' / ' + label[1]) + '">' + content + '</section>' for key, label, content in panels) + '</div></div>'
    body += '<p class="av-footer">' + bi('说明文字为界面释义；引文、数值与状态来自登记的冻结运行。显示不改变候选、快照或采纳状态。', 'UI explanations are editorial; quotes, values and statuses come from the registered frozen run. Viewing does not change candidate, snapshot or adoption state.') + '</p>'
    html = page('步骤验收', body)
    css = asset_text('acceptance_view.css')
    js = asset_text('acceptance_view.js')
    return html.replace('</head>', '<style>' + css + '</style></head>').replace('</body>', '<script>' + js + '</script></body>')
