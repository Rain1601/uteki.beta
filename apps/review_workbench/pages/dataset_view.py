"""Read-only database grid and source -> extraction -> normalized row lineage."""
from apps.review_workbench.assets import asset_text
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import urlencode, urlparse

from apps.review_workbench.pages.query_runs import collections, contained, e, amount, period
from apps.review_workbench.components.site_navigation import bi, company_tabs, crumb, page


def read_dataset(root, collection):
    import duckdb
    binding = collection['dataset']
    folder = contained(root, binding['path'])
    raw = (folder / 'manifest.json').read_bytes()
    if sha256(raw).hexdigest() != binding['manifest_sha256']:
        raise ValueError('Dataset manifest changed')
    manifest = json.loads(raw)
    for name, expected in manifest['files'].items():
        if sha256(contained(folder, name).read_bytes()).hexdigest() != expected:
            raise ValueError('Dataset artifact changed')
    with duckdb.connect(str(folder / 'research.duckdb'), read_only=True, config={
            'enable_external_access': 'false', 'autoinstall_known_extensions': 'false',
            'autoload_known_extensions': 'false', 'threads': '1', 'memory_limit': '128MB'}) as db:
        cursor = db.execute('SELECT o.* FROM observations o JOIN sources s USING(source_snapshot_id) '
                            'WHERE s.company_id = ? ORDER BY o.entity_id, o.metric_id, o.period_end, o.record_id',
                            [collection['company_id']])
        names = [c[0] for c in cursor.description]
        physical = [dict(zip(names, row)) for row in cursor.fetchall()]
        evidence = {row[0]: json.loads(row[1]) for row in db.execute(
            'SELECT e.evidence_id, e.payload FROM evidence e JOIN sources s USING(source_snapshot_id) WHERE s.company_id = ?',
            [collection['company_id']]).fetchall()}
        columns = db.execute("SELECT table_name, column_name, data_type, is_nullable "
                             "FROM information_schema.columns WHERE table_schema = 'main' "
                             "ORDER BY table_name, ordinal_position").fetchall()
    records = [json.loads(row['payload']) for row in physical]
    sources = [s for s in json.loads((folder / 'sources.json').read_text()) if s['company_id'] == collection['company_id']]
    metrics = json.loads((folder / 'metrics.json').read_text())
    return {'folder': folder, 'manifest': manifest, 'physical': physical, 'records': records,
            'sources': sources, 'metrics': metrics, 'evidence': evidence, 'columns': columns}


def fields(value, prefix=''):
    """Human-readable field/value rows, including original nested fields."""
    if isinstance(value, dict):
        if not value:
            yield prefix, '—'
        for key, item in value.items():
            yield from fields(item, prefix + ('.' if prefix else '') + key)
    elif isinstance(value, list):
        if not value:
            yield prefix, '[]'
        for i, item in enumerate(value):
            yield from fields(item, f'{prefix}[{i}]')
    else:
        yield prefix, 'NULL' if value is None else str(value)


def field_table(value):
    return '<table class="ds-fields"><tbody>' + ''.join('<tr><th>' + e(k) + '</th><td>' + e(v) + '</td></tr>' for k, v in fields(value)) + '</tbody></table>'


def compare(record):
    raw = record['origin']['raw_record']
    pairs = [('entity_id', raw.get('entity_id', raw.get('entity'))), ('metric_id', raw.get('metric')),
             ('period', raw.get('period')), ('value_decimal', raw.get('value_decimal', raw.get('value'))),
             ('upper_decimal', raw.get('upper')), ('unit', raw.get('unit')),
             ('value_relation', raw.get('value_relation')), ('denominator', raw.get('denominator')),
             ('modality', raw.get('modality')), ('dimensions', raw.get('dimensions'))]
    text = lambda v: '<br>'.join(e(k + ': ' if k else '') + e(x) for k, x in fields(v)) or '—'
    return '<div class="ds-scroll"><table class="ds-compare"><thead><tr><th>' + bi('字段', 'Field') + '</th><th>' + bi('抽取记录', 'Extracted record') + '</th><th>' + bi('入库记录', 'Normalized record') + '</th></tr></thead><tbody>' + ''.join(
        '<tr><th>' + e(k) + '</th><td>' + text(v) + '</td><td>' + text(record.get(k)) + '</td></tr>' for k, v in pairs) + '</tbody></table></div>'


def render_block(block):
    table = block.get('table')
    if not table:
        return '<p class="ds-source-text">' + e(block['text']) + '</p>'
    by_row = {}
    for cell in table['cells']:
        by_row.setdefault(cell['row'], []).append(cell)
    rendered = '<div class="ds-scroll"><table class="ds-original-table">'
    for _, cells in sorted(by_row.items()):
        rendered += '<tr>' + ''.join('<td colspan="' + str(c['colspan']) + '" rowspan="' + str(c['rowspan']) + '">' + e(c['text']) + '</td>' for c in sorted(cells, key=lambda c: c['column'])) + '</tr>'
    return rendered + '</table></div>'


def lineage(data, record, physical, collection):
    source = next(s for s in data['sources'] if s['source_snapshot_id'] == record['source_snapshot_id'])
    block_map = {b['block_id']: b for b in map(json.loads, contained(data['folder'], source['index_folder'] + '/blocks.jsonl').read_text().splitlines())}
    label = data['metrics'].get(record['metric_id'], {}).get('label', record['metric_id'])
    body = '<section id="record-detail" class="ds-detail"><h2>' + bi('这一行是怎么来的', 'How this row was produced') + '</h2><p>' + e(label) + ' / ' + e(record['entity_id']) + ' / ' + amount(record) + '</p>'
    body += '<div class="ds-chain"><span>' + bi('01 原始材料', '01 Original source') + '</span><span>' + bi('02 文档解析', '02 Document parsing') + '</span><span>' + bi('03 抽取记录', '03 Extracted record') + '</span><span>' + bi('04 规范化入库', '04 Normalized row') + '</span></div>'
    body += '<h3>' + bi('原始材料与解析内容', 'Original material & parsed content') + '</h3><p>' + e(source['form']) + ' / ' + e(source['period_end']) + ' / ' + bi('公开日期 ', 'Available from ') + e(source['available_at']) + '</p>'
    if urlparse(source['source_url']).scheme in ('https', 'http'):
        body += '<a href="' + e(source['source_url']) + '">' + bi('打开原始材料（官网）', 'Open original source (official site)') + '</a>'
    body += '<p class="qr-muted">' + bi('冻结文件：', 'Frozen file: ') + e(source['raw_file']) + '</p>'
    seen = set()
    for role in ('evidence_ids', 'qualifier_evidence_ids', 'question_evidence_ids'):
        for eid in record.get(role, []):
            ev = data['evidence'][eid]
            block = block_map[ev['block_id']]
            body += '<div class="ds-source"><strong>' + bi(*{'evidence_ids': ('取值依据', 'Value evidence'), 'qualifier_evidence_ids': ('限定条件', 'Qualifications'), 'question_evidence_ids': ('分析师问题', 'Analyst question')}[role]) + '</strong><blockquote>' + e(ev['quote']) + '</blockquote><small>' + e(ev['block_id']) + ' / p. ' + e(ev.get('pdf_page') or ev.get('reported_page')) + '</small>'
            if ev.get('number_metadata'):
                body += '<details><summary>' + bi('原始数字、尺度与单位', 'Original number, scale & unit') + '</summary>' + field_table(ev['number_metadata']) + '</details>'
            if ev['block_id'] not in seen:
                body += '<details><summary>' + bi('完整解析块 / 表格', 'Complete parsed block / table') + '</summary>' + render_block(block) + '</details>'
                seen.add(ev['block_id'])
            body += '</div>'
    method = bi('财务解析产物：依据 XBRL 上下文、期间、单位和表格定位抽取。', 'Financial extraction uses XBRL context, periods, units and table locators.') if 'value_decimal' in record['origin']['raw_record'] else bi('电话会抽取产物：模型抽取后，经显式来源适配器规范化。', 'Call extraction was produced by a model, then normalized by an explicitly scoped source adapter.')
    body += '<h3>' + bi('抽取前后字段对照', 'Extraction-to-database comparison') + '</h3><p>' + method + '</p>' + compare(record)
    body += '<p class="qr-muted">' + bi('NULL 表示该字段未独立填写，不表示原文没有提及。', 'NULL means no separate field value; the source may still express it.') + '</p>'
    body += '<details><summary>' + bi('查看完整抽取记录（字段表）', 'Complete extracted record (field table)') + '</summary>' + field_table(record['origin']['raw_record']) + '</details>'
    body += '<details><summary>' + bi('查看数据库物理列', 'Database physical columns') + '</summary>' + field_table({k: str(v) if v is not None else None for k, v in physical.items() if k != 'payload'}) + '<p>' + bi('payload 保存完整规范化记录，以下以字段表展开。', 'payload retains the full normalized record, expanded as fields below.') + '</p>' + field_table({k: v for k, v in record.items() if k != 'origin'}) + '</details>'
    body += '<h3>' + bi('保留了什么，仍有什么边界', 'Preservation & remaining limits') + '</h3><ul>'
    for note in collection['dataset'].get('metric_review', {}).get(record['metric_id'], []):
        body += '<li>' + bi(*note) + '</li>'
    body += '<li>' + bi('原文和抽取记录仍可回溯；这不证明抽取已经覆盖全文。', 'Sources and extracted records remain traceable; this does not establish exhaustive extraction.') + '</li></ul><details><summary>' + bi('规范化说明与输入文件', 'Normalization notes & input artifact') + '</summary><ul>' + ''.join('<li>' + e(n) + '</li>' for n in record['normalization_notes']) + '</ul><p>' + e(record['origin']['artifact']) + '</p></details></section>'
    return body


def render_dataset(root, registry, company, collection_id, record_id=None):
    collection = next((c for c in collections(registry, company['id']) if c['id'] == collection_id), None)
    if not collection:
        raise KeyError('Unknown company dataset collection')
    data = read_dataset(root, collection)
    by_id = {r['record_id']: (r, physical) for r, physical in zip(data['records'], data['physical'])}
    if record_id and record_id not in by_id:
        raise KeyError('Unknown dataset record')
    sources = {s['source_snapshot_id']: s for s in data['sources']}
    body = crumb(company, ('数据库明细', 'Database records')) + company_tabs(company['id'], 'data')
    body += '<style>' + asset_text('query_runs.css') + '\n' + asset_text('dataset_view.css') + '</style><div class="qr-workspace ds-workspace"><div class="qr-row"><h1>' + bi('数据库明细', 'Database records') + '</h1><a href="/companies/' + e(company['id']) + '/data/queries">' + bi('查看查询与 SQL', 'View queries & SQL') + '</a></div>'
    body += '<p>' + bi(f'{len(data["records"])} 条候选记录，来自 {len(sources)} 份材料。每行对应 observations 表的一行，不是独立事实计数。', f'{len(data["records"])} candidate rows from {len(sources)} sources. Each row is an observations row, not a unique-fact count.') + '</p>'
    body += '<p class="qr-muted">' + bi('直接读取所选 DuckDB 快照。点击任一行的“处理过程”，核对原文、抽取值和入库字段。', 'Read directly from the selected DuckDB snapshot. Open a row’s lineage to compare source, extraction and stored fields.') + '</p>'
    body += '<nav class="ds-jumps" aria-label="Dataset guide"><a href="#data-limits">' + bi('信息损耗与覆盖', 'Loss & coverage') + '</a><a href="#data-updates">' + bi('新增数据如何更新', 'How new data is added') + '</a></nav>'
    body += '<details class="ds-schema"><summary>' + bi('数据库 Schema：表、字段与类型', 'Database schema: tables, fields & types') + '</summary><p>' + bi('指标值以 DECIMAL 保存；分母、语气等完整语义存于 payload，不能只读取 value_decimal。', 'Values use DECIMAL; denominator, modality and full semantics live in payload. Reading value_decimal alone is insufficient.') + '</p><div class="ds-scroll"><table class="ds-fields"><thead><tr>' + ''.join('<th>' + bi(*label) + '</th>' for label in [('表', 'Table'), ('字段', 'Column'), ('类型', 'Type'), ('可为空', 'Nullable')]) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + e(value) + '</td>' for value in column) + '</tr>' for column in data['columns']) + '</tbody></table></div></details>'
    body += '<div class="ds-controls"><label>' + bi('搜索', 'Search') + '<input id="ds-search" type="search" placeholder="指标、实体、年份 / Metric, entity, year"></label><label>' + bi('指标', 'Metric') + '<select id="ds-metric"><option value="">' + '全部指标 / All metrics' + '</option>' + ''.join('<option value="' + e(m) + '">' + e(data['metrics'].get(m, {}).get('label', m)) + '</option>' for m in sorted({r['metric_id'] for r in data['records']})) + '</select></label><span id="ds-count" aria-live="polite"></span></div>'
    body += '<div class="ds-grid" tabindex="0" aria-label="Database records"><table><thead><tr>' + ''.join('<th>' + bi(*x) + '</th>' for x in [('行', 'Row'), ('实体', 'Entity'), ('指标', 'Metric'), ('数值 / 单位', 'Value / unit'), ('期间', 'Period'), ('关系', 'Relation'), ('分母', 'Denominator'), ('语气', 'Modality'), ('数据性质', 'Value kind'), ('来源', 'Source'), ('公开日期', 'Available'), ('详情', 'Lineage')]) + '</tr></thead><tbody>'
    for i, record in enumerate(data['records'], 1):
        source = sources[record['source_snapshot_id']]
        label = data['metrics'].get(record['metric_id'], {}).get('label', record['metric_id'])
        search = ' '.join(str(record[k]) for k in ('entity_id', 'metric_id', 'period', 'summary')) + ' ' + label
        href = '?' + urlencode({'collection': collection_id, 'record': record['record_id']}) + '#record-detail'
        cells = [str(i), e(record['entity_id']), e(label), amount(record), period(record['period']) if record['period'] else e(record['period_resolution']), e(record['value_relation']), e(record['denominator']) or '—', e(record['modality']) or '—', e(record['value_kind']), e(source['form'] + ' / ' + source['period_end']), e(record['available_at']), '<a href="' + e(href) + '">' + bi('处理过程', 'View lineage') + '</a>']
        body += '<tr data-search="' + e(search.lower()) + '" data-metric="' + e(record['metric_id']) + '"' + (' class="ds-selected"' if record['record_id'] == record_id else '') + '>' + ''.join('<td>' + v + '</td>' for v in cells) + '</tr>'
    body += '</tbody></table></div><p id="ds-empty" hidden>' + bi('没有匹配记录。', 'No matching records.') + '</p><p class="qr-muted">' + bi('表格可横向滚动；只读，候选数据未采纳。', 'Scroll horizontally to inspect columns. Read-only; candidates are not adopted.') + '</p>'
    if record_id:
        body += lineage(data, *by_id[record_id], collection)
    else:
        body += '<p class="ds-prompt">' + bi('选择任一行的“处理过程”，查看这一行从哪里来、转换了什么。', 'Open any row’s lineage to inspect its source and transformations.') + '</p>'
    body += '<section class="ds-boundaries" id="data-limits"><h2>' + bi('信息损耗与覆盖边界', 'Information loss & coverage limits') + '</h2><p>' + bi('尚未完成全文信息损耗的定量评估。以下是当前可以确认的边界。', 'No quantitative full-document loss audit has been completed. These are the currently established limits.') + '</p><ul>'
    body += ''.join('<li>' + bi(*note) + '</li>' for note in collection['dataset']['review_notes']) + '</ul><details><summary>' + bi('来源覆盖明细', 'Source coverage') + '</summary><table class="ds-fields"><thead><tr><th>' + bi('来源', 'Source') + '</th><th>' + bi('解析块 / 入库行 / 引用块', 'Parsed blocks / stored rows / cited blocks') + '</th></tr></thead><tbody>'
    for sid, source in sources.items():
        source_rows = [r for r in data['records'] if r['source_snapshot_id'] == sid]
        cited = {ev['block_id'] for ev in data['evidence'].values() if ev['source_snapshot_id'] == sid}
        body += '<tr><th>' + e(source['form'] + ' / ' + source['period_end']) + '</th><td>' + f'{source["block_count"]} / {len(source_rows)} / {len(cited)}' + '</td></tr>'
    body += '</tbody></table><p class="qr-muted">' + bi('引用块数量不是信息召回率；一个表格块可以包含多项事实。', 'Cited-block count is not information recall; one table block can contain many facts.') + '</p></details><p class="qr-muted">' + e(data['manifest']['snapshot_id']) + '</p></section>'
    body += '<section class="ds-boundaries" id="data-updates"><h2>' + bi('后续数据如何更新', 'How new data is added') + '</h2><p>' + bi('当前是显式配置、生成新快照的方式；还没有自动增量同步。', 'Updates currently use explicit configuration and a new snapshot; automatic incremental sync is not implemented.') + '</p><ol>' + ''.join('<li>' + bi(*note) + '</li>' for note in collection['dataset']['update_notes']) + '</ol><p class="qr-muted">' + bi('旧查询继续绑定旧 snapshot_id。新快照不等于已审核或已采纳，也不会自动替换旧分析的输入。', 'Existing queries remain pinned to their snapshot_id. A new snapshot is not approval or adoption, and does not automatically replace old analysis inputs.') + '</p></section></div><script>' + asset_text('dataset_view.js') + '</script>'
    return page('数据库明细', body)
